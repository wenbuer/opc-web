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


def _squeeze(s: str, limit: int = 90) -> str:
    """压成单行短文本：进度行只放一句话，多行长文本（表格等）不进 UI。"""
    return " ".join(str(s or "").split())[:limit]


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


def run_headless_sync(task_text: str, timeout: float = 600, purpose: str = "") -> str:
    """同步直跑一次（最终文本模式），返回文本。

    走配置的执行引擎；purpose 非空时按用途路由（config.engine_for），如 "prompt"。"""
    from .engines import get_engine
    return get_engine(config.engine_for(purpose)).run(
        task_text, timeout=timeout, on_progress=_progress_sink("")).text


def run_headless_task(task_text: str, timeout: float = 600, act: str = "", purpose: str = ""):
    """headless 最终文本模式：返回 (最终文本, 用量 dict|None)。

    走配置的执行引擎（purpose 非空时按用途路由，如 "execute"）。签名与语义与解耦前一致，
    chain / scheduler / server 无需改动；同时登记 act → 引擎名，供 kill_spawn 精确找对引擎。"""
    from .engines import get_engine
    eng = get_engine(config.engine_for(purpose))
    if act:
        with _EXEC_LOCK:
            _ACT_ENGINE[act] = eng.name
    try:
        res = eng.run(task_text, timeout=timeout, act=act, on_progress=_progress_sink(act))
    finally:
        if act:
            with _EXEC_LOCK:
                _ACT_ENGINE.pop(act, None)
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
