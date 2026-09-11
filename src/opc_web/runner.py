# -*- coding: utf-8 -*-
"""执行事件流与执行状态：自动执行链把阶段事件写进内存缓冲，工作台轮询显示。

本模块只剩两件事：

1. **事件与状态**：阶段事件缓冲（emit / events）与执行实时状态（exec_state）——
   两套执行引擎共用的**唯一进度出口**；
2. **对外入口**：run_headless_task / run_headless_sync / kill_spawn，按配置把活交给
   engines/ 里的实现（dsh 的细节全在 engines/dsh.py：命令、子进程、会话日志、强杀、技能）。

v1.16 精简：控制台不再自己 spawn 观测进程（原「直跑观测」），也不再读主会话遥测
JSONL——两条通道都从未产生过数据（《批阅台/运行监控/》与 ~/.dsh/opc-telemetry.jsonl
均不存在），UI 入口随「agent 执行监听」面板一并下线。
"""
import threading
import time

from . import config

_LOCK = threading.RLock()
_ACTIVE = {"events": [], "seq": 0}
_EXEC_LOCK = threading.Lock()
_EXEC_STATE = {}     # act -> {startedAt, tools, lastTool, lastText, beatMono, session}——执行实时状态值
_ACT_ENGINE = {}     # act -> 正在执行它的引擎名（按用途路由后，kill 要精确找对引擎）
_LAST_RUN = {}       # act -> 最近一次运行信息（引擎名 / 引擎侧会话标识 / 耗时），供事后追溯


def _squeeze(s: str, limit: int = 90) -> str:
    """压成单行短文本：进度行只放一句话，多行长文本（表格等）不进 UI。"""
    return " ".join(str(s or "").split())[:limit]


_LOG_DIR = "运行日志"     # 完整运行轨迹落盘处：《批阅台/运行日志/T-xxx-Sn.log》
_TRACE_MAX = 20000        # 单个轨迹块进事件流的字符上限（超出只在落盘文件里留全文）


def trace_path(act: str) -> "object":
    """某子任务的运行日志路径。act 来自查询参数，所以要掐掉路径分隔符防逃逸。"""
    safe = "".join(ch for ch in str(act or "") if ch.isalnum() or ch in "-_")
    return config.BATCH_ROOT / _LOG_DIR / (safe + ".log")


def read_trace(act: str, limit: int = 400000) -> str:
    """读某子任务的完整运行日志（「查看完整日志」用）；没有则返回空串。"""
    p = trace_path(act)
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


def read_trace_task(task_no: str) -> str:
    """一个任务下所有子任务的运行日志，按子任务分段拼起来。

    子任务逐个执行、编号有序，所以直接按文件名排序拼即可；没有日志的跳过。
    任务维度的记录就靠它 —— 不必再把轨迹实时灌进界面。"""
    d = trace_path(task_no + "-S1").parent
    if not d.is_dir():
        return ""
    parts = []
    for p in sorted(d.glob("%s-S*.log" % task_no)):
        try:
            parts.append("=" * 58 + chr(10) + "# " + p.stem + chr(10) + "=" * 58 + chr(10)
                         + p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return (chr(10) + chr(10)).join(parts)


def trace_list(role: str = "", limit: int = 40) -> list:
    """有哪些运行日志可看（最近的在前面）：{sub, role, task, started, result, size}。

    数据源是执行记录表（谁在什么时候跑的）叠加日志文件是否存在 ——
    只列真的留下日志的那些，点开就有全文。"""
    from . import store
    out = []
    for e in reversed(store.executions()):
        if role and str(e.get("role") or "") != role:
            continue
        sub = str(e.get("sub_no") or "")
        p = trace_path(sub)
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        out.append({"sub": sub, "role": str(e.get("role") or ""),
                    "task": str(e.get("task_no") or ""),
                    "started": str(e.get("started_at") or ""),
                    "result": str(e.get("result") or ""), "size": size})
        if len(out) >= limit:
            break
    return out


def _trace_emit(act: str, kind: str, text: str) -> None:
    """完整轨迹：一条事件进事件流（面板实时看），同时追加落盘（事后回看）。

    事件流常驻内存且有上限，所以过长的单块在事件里截断并标注；
    落盘文件始终是全文 —— 面板里的「查看完整日志」读的就是它。"""
    body = str(text or "")
    cut = len(body) > _TRACE_MAX
    _append({"type": "exec/trace",
             "data": {"sub": act, "kind": str(kind or "text"),
                      "text": body[:_TRACE_MAX] if cut else body, "truncated": cut}})
    try:
        p = trace_path(act)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(chr(10) + "## [" + str(kind or "text") + "] "
                     + time.strftime("%H:%M:%S") + chr(10) + body + chr(10))
    except Exception:
        pass


def run_info(act: str) -> dict:
    """最近一次 act 运行的信息：{engine, session, elapsed}。

    用途：把「这次子任务是谁跑的、落在哪个引擎会话上」记进 meta.json。
    用量或进度对不上时能直接回溯到具体会话 —— T-008-S2 到 T-013-S1 那批就是缺了这一环，
    事后只能按时间与任务文本去猜，猜不准（同一会话会被安到多个子任务头上）。"""
    with _EXEC_LOCK:
        return dict(_LAST_RUN.get(act) or {})


def exec_state() -> dict:
    """各执行中子任务的实时状态值（工作台 /api/run/events 的 state.exec 透出）。"""
    with _EXEC_LOCK:
        return {k: dict(v) for k, v in _EXEC_STATE.items()}


def _exec_beat(act: str, tools: int, last_tool: str, last_text: str, t0: float):
    """刷新心跳与状态值，并 emit 一条 exec/progress 进度事件。"""
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
    _append({"type": "exec/progress",
             "data": {"sub": act, "elapsed": int(now - t0), "tools": tools,
                      "lastTool": _squeeze(last_tool, 130), "lastText": _squeeze(last_text, 120)}})


def _progress_sink(act: str):
    """引擎进度回调：把引擎报来的 Progress 落到执行状态与事件流。

    dsh 与 api 共用这一条路：引擎只管报 Progress，落到什么状态、发什么事件由本函数决定。
    收到 finished=True（引擎跑完）时清掉该 act 的执行中状态 —— 引擎不直接碰本模块的状态。
    act 为空（没有子任务号的同步直跑）时不记录状态。"""
    if not act:
        return None
    t0 = time.monotonic()

    def _on_progress(p):
        if getattr(p, "finished", False):
            with _EXEC_LOCK:
                _EXEC_STATE.pop(act, None)
            return
        tr = getattr(p, "trace", None)          # 完整轨迹（心跳之外的全文通道）
        if tr and str(tr.get("text") or "").strip():
            _trace_emit(act, str(tr.get("kind") or "text"), str(tr["text"]))
        # 只带轨迹、不带任何心跳字段的回调不能进心跳：它会把已累计的操作数清零
        # （界面于是显示「操作 0 次」，明明跑了 57 次工具调用）。
        if tr and not (int(getattr(p, "tools", 0) or 0)
                       or str(getattr(p, "lastTool", "") or "")
                       or str(getattr(p, "lastText", "") or "")
                       or str(getattr(p, "session", "") or "")):
            return
        _exec_beat(act, int(getattr(p, "tools", 0) or 0),
                   str(getattr(p, "lastTool", "") or ""),
                   str(getattr(p, "lastText", "") or ""), t0)
        sess = str(getattr(p, "session", "") or "")
        if sess:
            with _EXEC_LOCK:
                _EXEC_STATE.setdefault(act, {})["session"] = sess

    return _on_progress


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


def _engine_ready(name: str) -> bool:
    """引擎环境是否就绪（preflight）：探命令、读配置，都很轻。

    典型场景：默认引擎是 dsh，但本机没装 —— 这时应当**直接**改用备用引擎，
    而不是先派一次、等它秒退再回退（那一次同样会花掉拆解或角色执行的时间）。
    自检每次都做：用户可能刚装好 dsh，缓存住反而会挡住它。"""
    try:
        from .engines import get_engine
        ok, _ = get_engine(name).preflight()
        return bool(ok)
    except Exception:
        return False


def _engine_failed(res) -> bool:
    """这次是「引擎没跑起来」还是「任务本身没做完」——只有前者值得回退重跑。

    - 取消（killed）不回退：用户/超时主动停的，重跑等于把它又拉起来；
    - 报错回退：没装 dsh、鉴权失败、启动异常，换引擎确实能救；
    - 秒退无产出回退：dsh 秒退（T-006 那种）属于引擎侧问题；
    - 跑了很久还是没产出**不回退**：那是任务的问题，两个引擎都会跑同样久，
      重跑只会重复劳动 + 重复烧钱，交回上层按「无产出」处理。"""
    if getattr(res, "killed", False):
        return False
    if getattr(res, "error", ""):
        return True
    if not str(getattr(res, "text", "") or "").strip():
        return float(getattr(res, "elapsed", 0.0) or 0.0) < float(config.tune("fallbackMaxElapsed"))
    return False


def _run_engine(task_text: str, timeout: float, act: str = "", purpose: str = "", max_steps=None):
    """跑一次任务：主引擎失败时按配置回退到备用引擎（默认 api 兜底 dsh）。

    回退会留痕（engine/fallback 事件），工作台详情能看到「谁失败了、换了谁、为什么」。"""
    from .engines import get_engine
    name = config.engine_for(purpose)
    alt = config.engine_fallback(name)
    if alt and not _engine_ready(name):
        # 主引擎环境不满足（如本机没装 dsh）→ 直接用备用引擎，不必让它先失败一次
        emit({"type": "engine/fallback",
              "data": {"purpose": purpose or "main", "from": name, "to": alt,
                       "reason": "环境自检未通过（未安装或未配置）"}})
        return _invoke(get_engine(alt), alt, task_text, timeout, act, max_steps)
    res = _invoke(get_engine(name), name, task_text, timeout, act, max_steps)
    if not alt or not _engine_failed(res):
        return res
    emit({"type": "engine/fallback",
          "data": {"purpose": purpose or "main", "from": name, "to": alt,
                   "reason": res.error or ("%s 秒退无产出" % int(res.elapsed or 0))}})
    return _invoke(get_engine(alt), alt, task_text, timeout, act, max_steps)


def _invoke(eng, name: str, task_text: str, timeout: float, act: str, max_steps=None):
    """调一次引擎：登记 act → 引擎名（kill 用），跑完留下运行信息（追溯用）。"""
    if act:
        with _EXEC_LOCK:
            _ACT_ENGINE[act] = name
    try:
        if max_steps:
            res = eng.run(task_text, timeout=timeout, act=act, on_progress=_progress_sink(act),
                          max_steps=max_steps)
        else:
            # 不传 max_steps：老签名/自建引擎照旧可用（接口上它是可选参数）
            res = eng.run(task_text, timeout=timeout, act=act, on_progress=_progress_sink(act))
    finally:
        if act and _ACT_ENGINE.get(act) == name:
            with _EXEC_LOCK:
                _ACT_ENGINE.pop(act, None)
    if act:
        with _EXEC_LOCK:
            _LAST_RUN[act] = {"engine": name,
                              "session": str(getattr(res, "session", "") or ""),
                              "elapsed": round(float(getattr(res, "elapsed", 0.0) or 0.0), 1)}
            if len(_LAST_RUN) > 200:            # 只留最近 200 条：够追溯，不涨内存
                for k in list(_LAST_RUN)[:100]:
                    _LAST_RUN.pop(k, None)
    return res


def run_headless_sync(task_text: str, timeout: float = 600, purpose: str = "") -> str:
    """同步直跑一次（最终文本模式），返回文本。

    走配置的执行引擎；purpose 非空时按用途路由（config.engine_for），如 "prompt"。"""
    return _run_engine(task_text, timeout, act="", purpose=purpose).text


def run_headless_task(task_text: str, timeout: float = 600, act: str = "", purpose: str = "",
                      max_steps=None):
    """headless 最终文本模式：返回 (最终文本, 用量 dict|None)。

    走配置的执行引擎（purpose 非空时按用途路由，如 "execute"）。签名与语义与解耦前一致，
    chain / scheduler / server 无需改动；同时登记 act → 引擎名，供 kill_spawn 精确找对引擎。"""
    res = _run_engine(task_text, timeout, act=act, purpose=purpose, max_steps=max_steps)
    return res.text, res.usage


def kill_spawn(act: str) -> bool:
    """终止 act 对应的运行（删除任务前调用）。

    引擎可按用途路由，同一个 act 由哪个引擎在跑只有 run_headless_task 知道：先查登记表，
    查不到（进程重启、表已清）再逐个引擎问，谁认领谁终止。"""
    from .engines import available, get_engine
    with _EXEC_LOCK:
        name = _ACT_ENGINE.get(act)
    if name:
        try:
            if get_engine(name).kill(act):
                return True
        except Exception:
            pass
    for other in available():
        if other == name:
            continue
        try:
            if get_engine(other).kill(act):
                return True
        except Exception:
            continue
    return False
