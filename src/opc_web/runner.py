# -*- coding: utf-8 -*-
"""执行事件流：自动执行链把阶段事件写进内存缓冲，工作台详情面板轮询显示。

v1.16 精简：控制台不再自己 spawn 观测进程（原「直跑观测」），也不再读主会话遥测
JSONL——两条通道都从未产生过数据（《批阅台/运行监控/》与 ~/.dsh/opc-telemetry.jsonl
均不存在），UI 入口随「agent 执行监听」面板一并下线。本模块现在只做两件事：
接收 chain 写入的阶段事件，以及为任务拆解同步直跑一次 dsh headless。
"""
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import config

_LOCK = threading.RLock()
_ACTIVE = {"events": [], "seq": 0}


def _child_env() -> dict:
    """dsh 子进程的环境：项目根 .env 打底 + 当前进程环境覆盖（环境变量优先于文件）。

    dsh 自己不读项目 .env，子进程只继承父进程环境；而控制台启动时并不加载 .env
    （只有「设置→模型接入」保存那一刻会往 os.environ 塞一次）。结果是手改 .env 或
    重启之后，界面显示「已配置 ✓」而 headless 实际拿不到密钥。这里每次 spawn 现读，
    顺带让改完 .env 无需重启。"""
    return {**config.read_env_file(), **os.environ}


def _append(ev: dict) -> int:
    with _LOCK:
        _ACTIVE["seq"] += 1
        _ACTIVE["events"].append({"seq": _ACTIVE["seq"], **ev})
        if len(_ACTIVE["events"]) > 6000:
            _ACTIVE["events"] = _ACTIVE["events"][-4000:]
        return _ACTIVE["seq"]


def emit(ev: dict) -> int:
    """公开事件入口：自动执行链把阶段事件写进来，前端详情面板增量轮询。"""
    return _append(ev)


def events(since: int = 0) -> dict:
    """自 since 之后的新事件（前端用返回的 state.seq 作为下次游标）。"""
    with _LOCK:
        return {"ok": True, "state": {"seq": _ACTIVE["seq"]},
                "events": [e for e in _ACTIVE["events"] if e["seq"] > since]}


def _spawn_headless(argv: list, timeout: float) -> bytes:
    """启动 dsh headless 子进程并收尾，返回其原始 stdout（stderr 合并）字节。

    超时语义：headless 只在 turn 结束后一次性打印 final 文本；因此无输出即任务未启动，
    超 timeout 强杀（防静默挂死泄漏进程树）。但执行路径用 --events-jsonl 时会边生成边输出，
    所以「有输出」并不代表即将结束 —— 若生成过长或挂死，无限等待会卡死调度（SCHED_STATE.busy 永不回 False）。
    故统一：无输出超 timeout 强杀；有输出后再给 timeout*3 的硬上限，超过也强杀（判为阻塞）。
    spawn 失败返回 b""。"""
    exe = shutil.which("dsh") or "dsh"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    si = subprocess.STARTUPINFO() if hasattr(subprocess, "STARTUPINFO") else None
    if si is not None:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    try:
        p = subprocess.Popen([exe, "--profile", "headless"] + argv,
                             cwd=str(config.ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             creationflags=flags, startupinfo=si, env=_child_env())
    except Exception:
        return b""
    chunks = []

    def _drain():
        try:
            for blk in iter(lambda: p.stdout.read(65536), b""):
                chunks.append(blk)
        except Exception:
            pass

    threading.Thread(target=_drain, daemon=True).start()
    t0 = time.monotonic()
    t_first = None        # 首个输出时刻（有输出 = 任务在活动，但不等同即将结束）

    def _kill():
        try:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, text=True)
        except Exception:
            pass
        try:
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    hard = max(timeout * 3, 1800.0)     # 有输出后的硬上限，防长生成/挂死卡住调度
    while True:
        if p.poll() is not None:
            break                       # 自然结束
        if chunks and t_first is None:
            t_first = time.monotonic()  # 首帧输出：任务开始活动
        now = time.monotonic()
        if t_first is None and now - t0 > timeout:
            _kill(); break              # 全程无输出且超时 → 判死
        if t_first is not None and now - t_first > hard:
            _kill(); break              # 有输出但迟迟不结束 → 判阻塞，防死锁
        time.sleep(0.5)
    try:
        p.stdout.close()
    except Exception:
        pass
    return b"".join(chunks)


def run_headless_sync(task_text: str, timeout: float = 600) -> str:
    """同步直跑 dsh headless（最终文本模式），返回 stdout。"""
    return _spawn_headless([task_text], timeout).decode("utf-8", "replace").strip()


def _decode_stdout(data: bytes) -> str:
    """dsh 在 Windows 下把 --events-jsonl 写成了 UTF-16LE（带 BOM）；按 BOM 解，否则 UTF-8。"""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16-le" if data[:2] == b"\xff\xfe" else "utf-16-be", errors="replace")
    return data.decode("utf-8", errors="replace")


def _dsh_sessions_dir() -> Path:
    """DSH 会话事件日志根：~/.dsh/sessions（DSH_HOME 可覆盖）。"""
    return Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh")) / "sessions"


def _usage_from_session(session_dir: Path) -> dict:
    """从一次会话的 session.jsonl.zstd 抽最终 token 用量。

    语义同 dsh-tokenledger 的 sampleOf：取最后一条 assistant/message 的 data.usage，
    兜底 assistant/chunk 里 data.chunk.type === 'usage' 的 usage。缺 zstandard / 无日志返回 None。"""
    zf = session_dir / "session.jsonl.zstd"
    if not zf.is_file():
        return None
    try:
        import zstandard as zstd
    except Exception:
        return None
    try:
        with zstd.ZstdDecompressor().stream_reader(open(zf, "rb")) as _s:
            text = _s.read().decode("utf-8", "replace")
    except Exception:
        return None
    last = None
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            ev = json.loads(ln)
        except Exception:
            continue
        data = ev.get("data")
        if not isinstance(data, dict):
            continue
        u = None
        if ev.get("type") == "assistant/message" and isinstance(data.get("usage"), dict):
            u = data["usage"]
        elif (ev.get("type") == "assistant/chunk" and isinstance(data.get("chunk"), dict)
              and data["chunk"].get("type") == "usage" and isinstance(data["chunk"].get("usage"), dict)):
            u = data["chunk"]["usage"]
        if u:
            last = {"inputTokens": int(u.get("inputTokens") or 0),
                    "outputTokens": int(u.get("outputTokens") or 0),
                    "cacheReadTokens": int(u.get("cacheReadTokens") or 0),
                    "reasoningTokens": int(u.get("reasoningTokens") or 0)}
    return last


def read_session_usage() -> dict:
    """定位本次 headless 调用最新写入的会话日志并抽取 token 用量。

    位置：~/.dsh/sessions/<cwd片段>/session-<uuid>/session.jsonl.zstd。
    优先取目录名含项目根 basename 的会话（避免与同机其它 dsh 会话混淆），按 mtime 最新。
    cwd = config.ROOT（headless 子进程 cwd）。无会话 / 无 zstandard / 无 usage 返回 None。"""
    sess = _dsh_sessions_dir()
    if not sess.is_dir():
        return None
    try:
        dirs = [d for d in sess.glob("*/session-*") if d.is_dir()]
    except OSError:
        return None
    cwdkey = Path(str(config.ROOT)).name
    if cwdkey:
        prefer = [d for d in dirs if cwdkey in str(d)]
        if prefer:
            dirs = prefer
    if not dirs:
        return None
    try:
        latest = max(dirs, key=lambda d: d.stat().st_mtime)
    except OSError:
        return None
    return _usage_from_session(latest)


def run_headless_task(task_text: str, timeout: float = 600):
    """headless 最终文本模式：返回 (最终文本, 用量 dict|None)。

    dsh 0.1.1-rc.2 的 headless profile 不再提供 --events-jsonl；用量改从 DSH
    持久化的会话日志（~/.dsh/sessions/<cwd>/session-<uuid>/session.jsonl.zstd）抽取，
    语义同 dsh-tokenledger（assistant/message.data.usage）。无日志或无 zstandard → usage None。"""
    text = _decode_stdout(_spawn_headless([task_text], timeout)).strip()
    return text, read_session_usage()
