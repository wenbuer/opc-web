# -*- coding: utf-8 -*-
"""DshEngine：DeepSeek Harness 的 headless 执行实现。

dsh 的全部细节都在本模块：命令拼装（node 直跑 bin.js 绕开 cmd.exe 8191 字符上限）、
子进程与存活判定、会话事件日志的心跳与用量抽取、强杀、可装配技能清单。
runner 只保留事件缓冲与执行状态（两套引擎共用），不再含任何 dsh 细节。

进度出口：本模块不直接碰 runner 的状态，一律通过 on_progress 回调外报
（base.Progress）；跑完再报一次 finished=True，让上层清掉「执行中」状态。

本模块**不导入 runner**（那是反向依赖）。跨模块只依赖 config 与 base。
"""
import codecs
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import zstandard as zstd

from .base import Engine, Progress, RunResult

from .. import config

_SESS_HEAD = 24          # 会话认领用的任务文本前缀长度
_BEAT_IDLE = 20.0        # 无新事件时的心跳间隔（秒）

_STATE_LOCK = threading.RLock()
_ACTIVE_SPAWN = {}       # act -> 运行中 headless 子进程 pid（删除任务时终止）
_LAST_SESSION = {}       # act -> 本次认领到的会话目录（抽 usage 用，比按 mtime 猜准）
_BEAT = {}               # act -> 最近一次会话事件心跳（单调时钟，存活判定用）


def _squeeze(s: str, limit: int = 90) -> str:
    """压成单行短文本：进度行只放一句话，多行长文本（表格等）不进 UI。"""
    return " ".join(str(s or "").split())[:limit]


def _ev_text(ev: dict) -> str:
    """事件的可见文本（user/assistant message 的 content 文本块）。"""
    d = ev.get("data") or {}
    blocks = ((d.get("message") or {}).get("content") if isinstance(d, dict) else None) or d.get("content") or []
    if isinstance(blocks, str):
        return blocks
    return " ".join(str(b.get("text") or "") for b in blocks
                    if isinstance(b, dict) and b.get("type") == "text")


_REASON_MARK = "dsh: reasoning:" + chr(10)   # dsh 每段思考的起始标记（见 dsh-headless streamReasoning）


def _trace(on_progress, t0: float, kind: str, text: str):
    """外报一个完整轨迹块（心跳之外的「全文」通道）。"""
    if on_progress is None or not str(text or "").strip():
        return
    on_progress(Progress(elapsed=int(time.monotonic() - t0),
                         trace={"kind": kind, "text": str(text)}))


def _decoder(first: bytes):
    """按首块 BOM 定 stderr 的编码（dsh 在 Windows 下可能写 UTF-16LE），默认 UTF-8。

    用**增量**解码器而不是逐块 decode：多字节字符会被块边界切开，
    逐块解会在边界处产生替换字符。"""
    if first[:2] == b"\xff\xfe":
        return codecs.getincrementaldecoder("utf-16-le")(errors="replace")
    if first[:2] == b"\xfe\xff":
        return codecs.getincrementaldecoder("utf-16-be")(errors="replace")
    return codecs.getincrementaldecoder("utf-8")(errors="replace")


def _emit_reasoning(buf: str, on_progress, t0: float) -> str:
    """把 buf 里**已封口**的思考段外报，返回还没封口的尾巴。

    dsh 把 reasoning 增量写在 stderr 上，每段以 "dsh: reasoning:\n" 开头、
    下一段开头之前就算一段结束（段内可含换行）。所以按这个标记切分即可 ——
    切出来的每一段就是它的一次「思考块」，实时推给面板就能看到此刻在想什么。"""
    while True:
        i = buf.find(_REASON_MARK)
        if i < 0:
            return buf                      # 还没等到下一段开头：整段仍未封口
        seg, buf = buf[:i], buf[i + len(_REASON_MARK):]
        if seg.strip():
            _trace(on_progress, t0, "reasoning", seg.rstrip())
    return buf


def _dsh_sessions_dir() -> Path:
    """DSH 会话事件日志根：~/.dsh/sessions（DSH_HOME 可覆盖）。"""
    return Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh")) / "sessions"


def _session_names() -> set:
    """当前已存在的会话目录名快照：spawn 前调用，线程只认之后新出现的会话。"""
    root = _dsh_sessions_dir()
    if not root.is_dir():
        return set()
    return {d.name for d in root.glob("*/session-*")}


def _decode_stdout(data: bytes) -> str:
    """dsh 在 Windows 下把 --events-jsonl 写成了 UTF-16LE（带 BOM）；按 BOM 解，否则 UTF-8。"""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16-le" if data[:2] == b"\xff\xfe" else "utf-16-be", errors="replace")
    return data.decode("utf-8", errors="replace")


_SESS_GLOB = "session*.jsonl.zstd"      # v3 起是 session.v3.jsonl.zstd，旧版 session.jsonl.zstd


def _sess_log(session_dir):
    """本次会话的事件日志文件（没有就返回 None）。

    DSH 0.1.5 起把事件日志改名为 session.v3.jsonl.zstd，旧的 session.jsonl.zstd 不再写；
    只认旧名会一直读到上一次运行留下的陈旧文件 —— 心跳不刷新（任务被当无活动强杀）、
    用量读不到、进度认领不到本次会话。这里按通配取最新一个文件，新旧名字都认。"""
    best = None
    for p in Path(session_dir).glob(_SESS_GLOB):
        try:
            if p.is_file() and (best is None or p.stat().st_mtime > best.stat().st_mtime):
                best = p
        except OSError:
            continue
    return best


def _usage_row(u: dict) -> dict:
    """一条 usage 记录 → 统一字段（缺的补 0）。"""
    return {"inputTokens": int(u.get("inputTokens") or 0),
            "outputTokens": int(u.get("outputTokens") or 0),
            "cacheReadTokens": int(u.get("cacheReadTokens") or 0),
            "reasoningTokens": int(u.get("reasoningTokens") or 0)}


def _usage_from_session(session_dir) -> dict:
    """从一次会话的事件日志抽 token 用量：**逐轮累加**（旧格式回落到最后一条）。

    每条 assistant/message 的 usage 是「该轮」的量，不是会话累计值：实测一次 9 轮任务，
    第 1 轮 in 4975/cache 7680，第 9 轮 in 256/cache 26240 —— 每轮只报「本轮重发的上下文里
    没命中缓存的那部分」。provider 按每轮重发的上下文计费，所以总消耗 = 各轮之和。
    只取最后一条会漏掉前面所有轮次（同一会话实测 174k 输入被记成 26k，少记 85%），
    而 api 引擎是逐轮累加的 —— 两个引擎的数字根本没法比，这才是「差距很大」的主因。

    旧格式（没有 assistant/message 的 usage，只有 assistant/chunk）
    保持原语义：取最后一条。缺 zstandard / 无日志返回 None。"""
    zf = _sess_log(session_dir)
    if zf is None:
        return None
    try:
        with open(zf, "rb") as fh, zstd.ZstdDecompressor().stream_reader(fh) as _s:
            text = _s.read().decode("utf-8", "replace")
    except Exception:
        return None
    total = None
    last_chunk = None
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
            last_chunk = _usage_row(data["chunk"]["usage"])
            continue
        if u:
            row = _usage_row(u)
            if total is None:
                total = row
            else:
                for k in total:
                    total[k] += row[k]
    return total if total is not None else last_chunk


def _ztime(d) -> float:
    zf = _sess_log(d)
    try:
        return zf.stat().st_mtime if zf else 0.0
    except OSError:
        return 0.0


def read_session_usage(since: float = 0.0, session_dir=None) -> dict:
    """定位本次 headless 调用最新写入的会话日志并抽取 token 用量。

    位置：~/.dsh/sessions/<cwd片段>/session-<uuid>/session.jsonl.zstd。
    优先取目录名含项目根 basename 的会话（避免与同机其它 dsh 会话混淆），按 mtime 最新。
    since 由 _run_prompt_dsh 传入「本次 headless 开始前的时刻」，据此排除那些在本次调用
    开始之前就已落盘的旧会话——因为多通道/并发执行时（拆解+各角色 headless+R1 判断派发）
    会同时写入多个会话，若只按全局最新 mtime 取，极易读到「另一条还在写/尚无 usage」的会话，
    导致 usage 读到 None 而不写 token。带 since 过滤后，本次 headless 的会话必然在 since 之后，
    可精确锁定本次调用。cwd = config.ROOT（headless 子进程 cwd）。无会话/无 zstandard/无 usage 返回 None。"""
    if session_dir is not None:
        # 已知会话（执行期间由 _watch_session 三重校验认领）：直接取，避开「按 mtime 猜」
        # 在并发执行下选错会话/选空的问题（T-008-S1 正常完成却没读到用量即此因）。
        return _usage_from_session(session_dir)
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


def _child_env() -> dict:
    """dsh 子进程的环境：项目根 .env 打底 + 当前进程环境覆盖（环境变量优先于文件）。

    dsh 自己不读项目 .env，子进程只继承父进程环境；而控制台启动时并不加载 .env
    （只有「设置→模型接入」保存那一刻会往 os.environ 塞一次）。结果是手改 .env 或
    重启之后，界面显示「已配置 ✓」而 headless 实际拿不到密钥。这里每次 spawn 现读，
    顺带让改完 .env 无需重启。"""
    return {**config.read_env_file(), **os.environ}


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


def _watch_session(act: str, p: subprocess.Popen, spawn_epoch: float, t0: float,
                   pre: set = None, prompt_head: str = "", on_progress=None):
    """跟踪本次 headless 的 dsh 会话事件日志（数据源 ~/.dsh/sessions/<cwd>/session-*.jsonl.zstd）。

    借鉴 dsh-better-sidebar 的 lastActivity：只取 tool/call 与 assistant/message 两类事件，
    反向折叠出「最近工具调用 + 最近文本」，忽略生命周期与 chunk 碎片；文本一律压成单行短句
    （多行内容进 UI 会被误读成截断）。

    会话认领三重校验，缺一就换下一个候选：① 目录名不在 spawn 前快照里（本次新出现）；
    ② 事件里的 cwd 等于项目根；③ 会话内存在与本次任务文本前缀一致的 user/message。
    只按 mtime 取最近会话会认领到别的会话——T-007-S1 曾把别的会话的表格文本当成自己的
    「最近文本」显示在工作台上。

    每次解析到新事件刷新 _BEAT 心跳（存活判定即「事件在增长」），并通过 on_progress 外报；
    无新事件时每 _BEAT_IDLE 秒补一次心跳，避免界面看起来卡住。"""
    root = _dsh_sessions_dir()
    pre = pre or set()
    sess = None
    seen = 0
    tools = 0
    last_tool = ""
    last_text = ""
    head = _squeeze(prompt_head, _SESS_HEAD)
    last_emit = 0.0

    def _report(tools_n: int, last_tool: str, last_text: str, sess_name: str = ""):
        """报一次进度：刷新心跳，并（若有回调）把这次活动外报给上层。"""
        now = time.monotonic()
        with _STATE_LOCK:
            _BEAT[act] = now
        if on_progress is None:
            return
        on_progress(Progress(elapsed=int(now - t0), tools=tools_n,
                             lastTool=last_tool, lastText=last_text, session=sess_name))

    while p.poll() is None:
        time.sleep(2)
        try:
            if sess is None:
                # 候选 = spawn 前快照里没有的会话目录，最新的先试（认领规则见函数说明）
                cands = []
                for d in root.glob("*/session-*"):
                    zf = _sess_log(d)
                    if d.name in pre or zf is None:
                        continue
                    cands.append((zf.stat().st_mtime, d))
                for _, d in sorted(cands, reverse=True):
                    zf = _sess_log(d)
                    if zf is None:
                        continue
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
            zf = _sess_log(d)
            if zf is None:
                continue
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
                        # 轨迹给全文参数（心跳只给 110 字摘要）
                        _trace(on_progress, t0, "tool",
                               name + " " + _squeeze(str(dd.get("arguments") or ""), 800))
                    elif ev.get("type") == "assistant/message":
                        full = _ev_text(ev).strip()
                        txt = _squeeze(full, 90)
                        if txt:
                            last_text = txt
                        if full:
                            _trace(on_progress, t0, "text", full)
                seen = len(evs)
                with _STATE_LOCK:
                    _LAST_SESSION[act] = d      # 抽 usage 时直接用这个会话，不再按 mtime 猜
                _report(tools, last_tool, last_text, d.name[-12:])
                last_emit = time.monotonic()
            elif time.monotonic() - last_emit > _BEAT_IDLE:
                # 周期心跳：暂无新事件也刷新一次，界面能看出「还在跑」而不是卡住
                _report(tools, last_tool, last_text)
                last_emit = time.monotonic()
        except Exception:
            continue


def _spawn_headless(argv: list, timeout: float, act: str = "", on_progress=None) -> bytes:
    """启动 dsh headless 子进程并收尾，返回其原始 stdout（stderr 合并）字节。

    存活语义（v1.17）：headless 只在 turn 结束后一次性打印 final 文本，stdout 全程静默，
    因此「无输出」不能当死亡判据 —— 900 秒无输出强杀曾把正在干活 15+ 分钟的 R3/R4 误判阻塞。
    现在以 _watch_session 追踪的会话事件心跳为准：事件持续增长即存活；心跳停摆超 timeout
    才判死（真挂死），另有 timeout*3 的总时长硬上限兜底。act 为空时退回纯 stdout 语义。
    stdout 只放最终答案，stderr 放推理流（headless 把 reasoning 增量直接写 stderr，前缀
    「dsh: reasoning:」）与错误行。两者必须分开读：合流之后整段思考会被当成「最终文本」
    返回给用户 —— 用户等了三分钟，等到的是一份思考过程而不是答案。
    spawn 失败返回 (b"", b"")。"""
    base = _dsh_command()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    si = subprocess.STARTUPINFO() if hasattr(subprocess, "STARTUPINFO") else None
    if si is not None:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    pre_sessions = _session_names() if act else set()   # spawn 前的会话快照（认领用）
    try:
        p = subprocess.Popen(base + ["--profile", "headless"] + argv,
                             cwd=str(config.ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=flags, startupinfo=si, env=_child_env())
    except Exception:
        return b"", b""
    if act:
        with _STATE_LOCK:
            _ACTIVE_SPAWN[act] = p.pid
    t0 = time.monotonic()
    out_chunks, err_chunks = [], []

    def _drain(stream, sink, watch=False):
        dec, buf = None, ""
        try:
            for blk in iter(lambda: stream.read(65536), b""):
                sink.append(blk)
                if not watch or on_progress is None:
                    continue
                if dec is None:
                    dec = _decoder(blk)
                buf += dec.decode(blk)
                buf = _emit_reasoning(buf, on_progress, t0)
        except Exception:
            pass                # 两个流各排一个线程：任一个不读满都可能把子进程堵在写管道上
        if watch and on_progress is not None and buf.strip():
            _emit_reasoning(buf + chr(10), on_progress, t0)   # 收尾：最后一段没等到下一段开头也报

    for _stream, _sink, _watch in ((p.stdout, out_chunks, False), (p.stderr, err_chunks, True)):
        threading.Thread(target=_drain, args=(_stream, _sink, _watch), daemon=True).start()
    if act:
        threading.Thread(target=_watch_session,
                         args=(act, p, time.time(), t0, pre_sessions,
                               argv[-1] if argv else "", on_progress),
                         daemon=True).start()
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
        if out_chunks and t_first is None:
            t_first = time.monotonic()  # 首帧输出：任务开始活动
        now = time.monotonic()
        last = t_first
        if act:
            with _STATE_LOCK:
                beat = _BEAT.get(act) or 0
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
    for _stream in (p.stdout, p.stderr):
        try:
            _stream.close()
        except Exception:
            pass
    if act:
        with _STATE_LOCK:
            _ACTIVE_SPAWN.pop(act, None)
            _BEAT.pop(act, None)
    # 结束信号不在这里报：最终输出的轨迹块还在后面（_run_prompt_dsh 解出文本才报），
    # 先报 finished 会被那条轨迹重新建出「执行中」状态，界面上永远停在进行中。
    return b"".join(out_chunks), b"".join(err_chunks)


def _kill_spawn(act: str) -> bool:
    """终止由 act 对应的运行中 headless 子进程（连同其子进程树）。

    删除任务前调用：若有执行中/待派/已派子任务，先 taskkill 掉 headless，再删任务，
    避免运行中产出在删除后被重建（孤儿执行与残留文件）。返回是否真的终止了进程。"""
    with _STATE_LOCK:
        pid = _ACTIVE_SPAWN.pop(act, None)
    if not pid:
        return False
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
        return True
    except Exception:
        return False


def _stderr_errors(raw: str) -> str:
    """stderr 里的失败原因（`dsh: <code>: <msg>` 那几行）。

    推理流也在 stderr 上，但它不是答案：只取 dsh 明确报错的行，其余丢弃 ——
    否则一次失败会被上层当成「有产出」，既看不到真实原因，也不会回退到备用引擎。"""
    out = [ln.strip() for ln in str(raw or "").splitlines()
           if ln.strip().startswith("dsh: ") and ln.strip() != "dsh: reasoning:"]
    return " / ".join(out[-3:])[:300]


def _run_prompt_dsh(task_text: str, timeout: float, act: str = "", on_progress=None):
    """dsh 引擎的底层实现。

    返回 (最终文本, 用量 dict|None, 会话标识)。headless 只在结束时打印 final 文本；
    用量从 DSH 会话日志（~/.dsh/sessions/<cwd>/session-<uuid>/session.jsonl.zstd）抽取，
    会话由 _watch_session 三重校验认领，避免并发下认领到别的会话。"""
    base = time.time()
    tm0 = time.monotonic()
    raw, err = _spawn_headless([task_text], timeout, act, on_progress)
    text = _decode_stdout(raw).strip()
    if not text:
        # 没有产出：把 stderr 里的失败原因回传，别让上层只看到一片空白
        text = _stderr_errors(_decode_stdout(err))
    _trace(on_progress, tm0, "final", text)   # 最终输出全文进轨迹（心跳只带 120 字）
    if on_progress:                          # 结束信号放最后：上层据此清掉「执行中」状态
        on_progress(Progress(finished=True, elapsed=int(time.monotonic() - tm0)))
    with _STATE_LOCK:
        claimed = _LAST_SESSION.pop(act, None) if act else None
    sess = Path(claimed).name[-12:] if claimed else ""
    return text, read_session_usage(base, claimed), sess


class DshEngine(Engine):
    name = "dsh"
    label = "DSH（DeepSeek Harness）"
    description = "调用 dsh headless 执行，自带工具沙箱与技能生态；进度取自会话日志"
    cost = ("每次执行是一整个 DSH 会话：自带系统提示、工具定义与技能生态，单轮上下文一万到数万 token，"
            "其中约九成命中缓存按低价计费。能跑需要沙箱的技能，代价是上下文天然比直连 API 大。")

    def capabilities(self) -> dict:
        return {"tools": True, "streaming": True, "usage": True, "skills": True, "sandbox": True}

    def preflight(self):
        if not shutil.which("dsh"):
            return False, "未找到 dsh 命令：请安装 @deepseek-ai/dsh，或把其 bin 目录加入 PATH"
        cmd = _dsh_command()
        return True, "dsh 命令可用：" + " ".join(str(x) for x in cmd[:2])

    def run(self, prompt: str, *, timeout: float = 600, act: str = "",
            cwd=None, on_progress=None, max_steps=None) -> RunResult:
        t0 = time.monotonic()
        try:
            text, usage, session = _run_prompt_dsh(prompt, timeout, act, on_progress)
        except Exception as e:                      # 启动失败/编码异常等
            return RunResult(error="dsh 执行异常：%s" % e, elapsed=time.monotonic() - t0)
        return RunResult(text=text or "", usage=usage, session=session or "",
                         elapsed=time.monotonic() - t0)

    def kill(self, act: str) -> bool:
        return bool(_kill_spawn(act))

    # 注：可装配技能的来源扫描在 opc_web.skills，不在这里 —— 技能是项目资产（prompt 的一部分），
    # 与引擎无关；本引擎只在 capabilities 里声明「能直接执行技能里需要工具的步骤」。
