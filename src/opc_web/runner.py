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

import zstandard as zstd

from . import config

_LOCK = threading.RLock()
_ACTIVE = {"events": [], "seq": 0}
_ACTIVE_SPAWN = {}   # act(key: 子任务号) -> 运行中 headless 子进程 pid，供删除任务时终止
_EXEC_LOCK = threading.Lock()
_EXEC_STATE = {}     # act -> {startedAt, tools, lastTool, lastText, beatMono, session}——执行实时状态值
_LAST_SESSION = {}   # act -> 本次 headless 认领到的会话目录（抽 usage 用，比按 mtime 猜准）


def exec_state() -> dict:
    """各执行中子任务的实时状态值（工作台 /api/run/events 的 state.exec 透出）。"""
    with _EXEC_LOCK:
        return {k: dict(v) for k, v in _EXEC_STATE.items()}


def _exec_beat(act: str, tools: int, last_tool: str, last_text: str, t0: float):
    """刷新心跳与状态值（事件追踪线程专用），并节流 emit 进度事件。"""
    now = time.monotonic()
    with _EXEC_LOCK:
        st = _EXEC_STATE.setdefault(act, {"startedAt": time.strftime("%H:%M:%S", time.localtime()),
                                          "tools": 0, "lastTool": "", "lastText": "",
                                          "beatMono": now - 999, "session": ""})
        st["tools"] = tools
        if last_tool:
            st["lastTool"] = last_tool
        if last_text:
            st["lastText"] = last_text
        st["beatMono"] = now
        st["elapsed"] = int(now - t0)      # 已运行秒数（首页「调度与用量」直接读）
        snap = dict(st)
    _append({"type": "exec/progress",
             "data": {"sub": act, "elapsed": int(now - t0), "tools": tools,
                      "lastTool": _squeeze(last_tool, 130), "lastText": _squeeze(last_text, 120)}})


_SESS_HEAD = 24          # 会话认领用的任务文本前缀长度
_BEAT_IDLE = 20.0        # 无新事件时的心跳间隔（秒）


def _session_names() -> set:
    """当前已存在的会话目录名快照：spawn 前调用，线程只认之后新出现的会话。"""
    root = _dsh_sessions_dir()
    if not root.is_dir():
        return set()
    return {d.name for d in root.glob("*/session-*")}


def _ev_text(ev: dict) -> str:
    """事件的可见文本（user/assistant message 的 content 文本块）。"""
    d = ev.get("data") or {}
    blocks = ((d.get("message") or {}).get("content") if isinstance(d, dict) else None) or d.get("content") or []
    if isinstance(blocks, str):
        return blocks
    return " ".join(str(b.get("text") or "") for b in blocks
                    if isinstance(b, dict) and b.get("type") == "text")


def _squeeze(s: str, limit: int = 90) -> str:
    """压成单行短文本：进度行只放一句话，多行长文本（表格等）不进 UI。"""
    return " ".join(str(s or "").split())[:limit]


def _watch_session(act: str, p: subprocess.Popen, spawn_epoch: float, t0: float,
                   pre: set = None, prompt_head: str = ""):
    """跟踪本次 headless 的 dsh 会话事件日志（数据源 ~/.dsh/sessions/<cwd>/session-*.jsonl.zstd）。

    借鉴 dsh-better-sidebar 的 lastActivity：只取 tool/call 与 assistant/message 两类事件，
    反向折叠出「最近工具调用 + 最近文本」，忽略生命周期与 chunk 碎片；文本一律压成单行短句
    （多行内容进 UI 会被误读成截断）。

    会话认领三重校验，缺一就换下一个候选：① 目录名不在 spawn 前快照里（本次新出现）；
    ② 事件里的 cwd 等于项目根；③ 会话内存在与本次任务文本前缀一致的 user/message。
    只按 mtime 取最近会话会认领到别的会话——T-007-S1 曾把别的会话的表格文本当成自己的
    「最近文本」显示在工作台上。

    每次解析到新事件刷新 _EXEC_STATE 心跳（存活判定即「事件在增长」），并 emit
    exec/progress；无新事件时每 _BEAT_IDLE 秒补一次心跳，避免界面看起来卡住。"""
    root = _dsh_sessions_dir()
    pre = pre or set()
    sess = None
    seen = 0
    tools = 0
    last_tool = ""
    last_text = ""
    head = _squeeze(prompt_head, _SESS_HEAD)
    last_emit = 0.0
    while p.poll() is None:
        time.sleep(2)
        try:
            if sess is None:
                # 候选 = spawn 前快照里没有的会话目录，最新的先试（认领规则见函数说明）
                cands = []
                for d in root.glob("*/session-*"):
                    zf = d / "session.jsonl.zstd"
                    if d.name in pre or not zf.is_file():
                        continue
                    cands.append((zf.stat().st_mtime, d))
                for _, d in sorted(cands, reverse=True):
                    zf = d / "session.jsonl.zstd"
                    with open(zf, "rb") as fh:
                        raw = zstd.ZstdDecompressor().stream_reader(fh).read()
                    evs = [json.loads(x) for x in raw.decode("utf-8", "replace").splitlines() if x.strip()]
                    cwd = next((ev.get("cwd", "") for ev in evs if ev.get("type") == "session"), "")
                    if str(cwd).rstrip("\\").lower() != str(config.ROOT).rstrip("\\").lower():
                        continue
                    if head and not any(head[:12] in _ev_text(ev)
                                        for ev in evs if ev.get("type") == "user/message"):
                        continue                # 不是本次任务的会话，换下一个候选
                    sess = (d, evs)
                    break
                if sess is None:
                    continue
                # seen 保持 0：认领到的会话里的事件全属本次任务
            d, _ = sess
            zf = d / "session.jsonl.zstd"
            with open(zf, "rb") as fh:
                raw = zstd.ZstdDecompressor().stream_reader(fh).read()
            evs = [json.loads(x) for x in raw.decode("utf-8", "replace").splitlines() if x.strip()]
            if len(evs) > seen:
                for ev in evs[seen:]:
                    if ev.get("type") == "tool/call":
                        dd = ev.get("data") or {}
                        name = str(dd.get("name") or "?")
                        brief = _squeeze(str(dd.get("arguments") or ""), 110)
                        tools += 1
                        last_tool = (name + " " + brief).strip()
                    elif ev.get("type") == "assistant/message":
                        txt = _squeeze(_ev_text(ev), 90)
                        if txt:
                            last_text = txt
                seen = len(evs)
                with _EXEC_LOCK:
                    _EXEC_STATE.setdefault(act, {})["session"] = d.name[-12:]
                    _LAST_SESSION[act] = d          # 抽 usage 时直接用这个会话，不再按 mtime 猜
                _exec_beat(act, tools, last_tool, last_text, t0)
                last_emit = time.monotonic()
            elif time.monotonic() - last_emit > _BEAT_IDLE:
                # 周期心跳：暂无新事件也刷新一次，界面能看出「还在跑」而不是卡住
                _exec_beat(act, tools, last_tool, last_text, t0)
                last_emit = time.monotonic()
        except Exception:
            continue


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
        return {"ok": True, "state": {"seq": _ACTIVE["seq"], "exec": exec_state()},
                "events": [e for e in _ACTIVE["events"] if e["seq"] > since]}


def _dsh_command() -> list:
    """dsh 启动命令：优先 node 直跑包内 bin.js。

    npm 的 dsh.cmd shim 经 cmd.exe 中转，命令行上限仅 8191 字符 —— 长 prompt
    （角色卡全文 + 决策上下文轻松过万）会被系统以「命令行太长。」秒杀，
    GBK 错误文本再被 stdout 解码固化成一串乱码（T-006 两次秒退的真凶）。
    node 直跑 lib/bin.js 走 CreateProcessW 原生上限 32767 字符，余量充足。"""
    exe = shutil.which("dsh")
    if exe:
        js = Path(exe).parent / "node_modules" / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
        node = shutil.which("node")
        if js.is_file() and node:
            return [node, str(js)]
    return ["dsh"]


def _spawn_headless(argv: list, timeout: float, act: str = "") -> bytes:
    """启动 dsh headless 子进程并收尾，返回其原始 stdout（stderr 合并）字节。

    存活语义（v1.17）：headless 只在 turn 结束后一次性打印 final 文本，stdout 全程静默，
    因此「无输出」不能当死亡判据 —— 900 秒无输出强杀曾把正在干活 15+ 分钟的 R3/R4 误判阻塞。
    现在以 _watch_session 追踪的会话事件心跳为准：事件持续增长即存活；心跳停摆超 timeout
    才判死（真挂死），另有 timeout*3 的总时长硬上限兜底。act 为空时退回纯 stdout 语义。
    spawn 失败返回 b""。"""
    base = _dsh_command()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    si = subprocess.STARTUPINFO() if hasattr(subprocess, "STARTUPINFO") else None
    if si is not None:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    pre_sessions = _session_names() if act else set()   # spawn 前的会话快照（认领用）
    try:
        p = subprocess.Popen(base + ["--profile", "headless"] + argv,
                             cwd=str(config.ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             creationflags=flags, startupinfo=si, env=_child_env())
    except Exception:
        return b""
    if act:
        _ACTIVE_SPAWN[act] = p.pid
    chunks = []

    def _drain():
        try:
            for blk in iter(lambda: p.stdout.read(65536), b""):
                chunks.append(blk)
        except Exception:
            pass

    threading.Thread(target=_drain, daemon=True).start()
    if act:
        threading.Thread(target=_watch_session,
                         args=(act, p, time.time(), time.monotonic(), pre_sessions,
                               argv[-1] if argv else ""),
                         daemon=True).start()
    t0 = time.monotonic()
    t_first = None        # stdout 首帧时刻（headless 期末才打印，平时靠会话事件心跳）

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

    hard = max(timeout * 3, 1800.0)     # 总时长硬上限，防长生成/挂死卡住调度
    while True:
        if p.poll() is not None:
            break                       # 自然结束
        if chunks and t_first is None:
            t_first = time.monotonic()  # 首帧输出：任务开始活动
        now = time.monotonic()
        last = t_first
        if act:
            beat = (_EXEC_STATE.get(act) or {}).get("beatMono") or 0
            if beat > (last or 0):
                last = beat             # 会话事件心跳 = 真实的活动信号
        if last is None:
            if now - t0 > timeout:
                _kill(); break          # 全程无任何活动且超时 → 判死
        elif now - last > timeout:
            _kill(); break              # 心跳停摆超 timeout（事件不再增长）→ 真挂死
        if now - t0 > hard:
            _kill(); break              # 总时长硬上限 → 判阻塞
        time.sleep(0.5)
    try:
        p.stdout.close()
    except Exception:
        pass
    if act:
        _ACTIVE_SPAWN.pop(act, None)
        with _EXEC_LOCK:
            _EXEC_STATE.pop(act, None)
    return b"".join(chunks)


def run_headless_sync(task_text: str, timeout: float = 600) -> str:
    """同步直跑一次（最终文本模式），返回文本。走配置的执行引擎（默认 dsh）。"""
    from .engines import get_engine
    return get_engine().run(task_text, timeout=timeout).text


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
        with open(zf, "rb") as fh, zstd.ZstdDecompressor().stream_reader(fh) as _s:
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


def read_session_usage(since: float = 0.0, session_dir=None) -> dict:
    """定位本次 headless 调用最新写入的会话日志并抽取 token 用量。

    位置：~/.dsh/sessions/<cwd片段>/session-<uuid>/session.jsonl.zstd。
    优先取目录名含项目根 basename 的会话（避免与同机其它 dsh 会话混淆），按 mtime 最新。
    since 由 run_headless_task 传入「本次 headless 开始前的时刻」，据此排除那些在本次调用
    开始之前就已落盘的旧会话——因为多通道/并发执行时（拆解+各角色 headless+R1 判断派发）
    会同时写入多个会话，若只按全局最新 mtime 取，极易读到「另一条还在写/尚无 usage」的会话，
    导致 usage 读到 None 而不写 token。带 since 过滤后，本次 headless 的会话必然在 since 之后，
    可精确锁定本次调用。cwd = config.ROOT（headless 子进程 cwd）。无会话/无 zstandard/无 usage 返回 None。"""
    if session_dir is not None:
        # 已知会话（执行期间由 _watch_session 三重校验认领）：直接取，避开「按 mtime 猜」
        # 在并发执行下选错会话/选空的问题（T-008-S1 正常完成却没读到用量即此因）。
        return _usage_from_session(Path(session_dir))
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

    def _ztime(d):
        zf = d / "session.jsonl.zstd"
        try:
            return zf.stat().st_mtime if zf.is_file() else 0.0
        except OSError:
            return 0.0

    if since:
        now = [d for d in dirs if _ztime(d) >= since]     # 本次 headless 会话必然在 since 之后落盘
        if not now:
            return None        # 本次调用没有留下会话日志（如 headless 秒退）—— 宁缺勿错，
        dirs = now             #   绝不拿旧会话的 usage 冒充（T-006：R3 秒退未落日志，读到了拆解会话的 token）
    try:
        latest = max(dirs, key=_ztime)
    except OSError:
        return None
    return _usage_from_session(latest)


def _run_prompt_dsh(task_text: str, timeout: float, act: str = ""):
    """dsh 引擎的底层实现（阶段 1 暂寄本模块，阶段 2 搬入 engines/dsh.py）。

    返回 (最终文本, 用量 dict|None, 会话标识)。headless 只在结束时打印 final 文本；
    用量从 DSH 会话日志（~/.dsh/sessions/<cwd>/session-<uuid>/session.jsonl.zstd）抽取，
    会话由 _watch_session 三重校验认领，避免并发下认领到别的会话。"""
    base = time.time()
    text = _decode_stdout(_spawn_headless([task_text], timeout, act)).strip()
    with _EXEC_LOCK:
        claimed = _LAST_SESSION.pop(act, None) if act else None
    sess = Path(claimed).name[-12:] if claimed else ""
    return text, read_session_usage(base, claimed), sess


def run_headless_task(task_text: str, timeout: float = 600, act: str = ""):
    """headless 最终文本模式：返回 (最终文本, 用量 dict|None)。走配置的执行引擎。

    解耦后本函数不再直接碰 dsh：由 engines.get_engine() 选实现（默认 DshEngine）。
    签名与语义保持不变，chain / scheduler / server 无需改动。"""
    from .engines import get_engine
    res = get_engine().run(task_text, timeout=timeout, act=act)
    return res.text, res.usage


def kill_spawn(act: str) -> bool:
    """终止 act 对应的运行（删除任务前调用）。走配置的执行引擎。"""
    from .engines import get_engine
    return get_engine().kill(act)


def _kill_spawn(act: str) -> bool:
    """终止由 act 对应的运行中 headless 子进程（连同其子进程树）。

    删除任务前调用：若有执行中/待派/已派子任务，先 taskkill 掉 headless，再删任务，
    避免运行中产出在删除后被重建（孤儿执行与残留文件）。返回是否真的终止了进程。"""
    pid = _ACTIVE_SPAWN.pop(act, None)
    if not pid:
        return False
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
        return True
    except Exception:
        return False
