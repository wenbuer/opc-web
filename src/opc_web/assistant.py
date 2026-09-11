# -*- coding: utf-8 -*-
"""R1 助理「临时会话」：悬浮窗里的问答，**刻意不进任务流程**。

与任务链路的区别（这是设计，不是遗漏）：
- **不落台账**：不调 store.add_task、不建子任务、不写回报 —— 一次问答就是一次问答；
- **单独记账**：每次问答的用量追加到《批阅台/临时会话.jsonl》，Token 统计里单列一项，
  既不污染任务统计，也不会凭空消失；
- **上下文按需**：给 R1 一段项目现状摘要（任务概况 / 档案 / 简报），够回答
  「现在什么情况」这类问题，不用把整条任务链塞进去。

复用引擎入口 run_headless_task（act 传空 → 不登记执行状态），所以换引擎、
按用途路由、失败回退这些行为与任务链路完全一致。
"""
import datetime
import json

from . import config, runner

LOG_REL = "批阅台/临时会话.jsonl"


def _path():
    return config.ROOT / LOG_REL


def records(limit: int = 0) -> list:
    """历史问答（按写入顺序）。文件不存在或损坏一律当作空，不抛异常。"""
    p = _path()
    if not p.is_file():
        return []
    out = []
    try:
        for ln in config.read_text(p).splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    except Exception:
        return []
    return out[-limit:] if limit else out


def totals() -> dict:
    """临时会话用量合计 —— Token 统计里的「临时会话」那一项。"""
    t = {"in": 0, "out": 0, "count": 0}
    for r in records():
        u = r.get("usage") or {}
        t["in"] += int(u.get("inputTokens") or 0) + int(u.get("cacheReadTokens") or 0)
        t["out"] += int(u.get("outputTokens") or 0)
        t["count"] += 1
    return t


def _append(rec: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + chr(10))


def _context() -> str:
    """项目现状摘要：任务概况 + 知识库与简报条数。够答「现在什么情况」，不做全量注入。"""
    lines = []
    try:
        from . import store
        ts = store.tasks()
        done = sum(1 for t in ts if str(t.get("status") or "") == "完成")
        busy = sum(1 for t in ts if str(t.get("status") or "") in ("执行中", "已派"))
        wait = len(ts) - done - busy
        lines.append("- 任务：共 %d 条（完成 %d / 进行中 %d / 待处理 %d）" % (len(ts), done, busy, max(0, wait)))
        last = ts[-3:] if len(ts) > 3 else ts
        for t in last:
            brief = " ".join(str(t.get("task") or "").split())[:60]     # 压单行：换行会把摘要撑散
            lines.append("  · %s [%s] %s" % (t.get("no"), t.get("status"), brief))
    except Exception:
        pass
    try:
        from . import knowledge
        kb = knowledge.kb_entries()
        lines.append("- 知识库：%d 篇档案" % len(kb))
    except Exception:
        pass
    try:
        from . import knowledge
        d = knowledge.latest_daily()
        if d:
            lines.append("- 最新简报：%s" % d[0].get("date"))
    except Exception:
        pass
    return chr(10).join(lines) if lines else "（项目现状读取失败，按已知信息回答即可）"


def _prompt(q: str) -> str:
    return (
        "你是 OPC 项目的老板助理 R1，现在和 R0（老板）做一次**临时答疑**。"
        + chr(10) + "规则：" + chr(10)
        + "- 只回答问题：不要新建任务、不要派发角色、不要输出任务编号与流程话术；" + chr(10)
        + "- 需要查文件就用工具去看，别凭印象猜；回答先给结论、再给依据，简短直接。" + chr(10) + chr(10)
        + "【项目现状】" + chr(10) + _context() + chr(10) + chr(10)
        + "【R0 的问题】" + chr(10) + q
    )


def ask(q: str, timeout: float = 240) -> dict:
    """问一句、答一句。不建任务、不派角色；用量记进临时会话账本。"""
    q = str(q or "").strip()
    if not q:
        return {"ok": False, "msg": "问题为空"}
    text, usage = runner.run_headless_task(_prompt(q), timeout=timeout, act="", purpose="prompt")
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "q": q, "a": (text or "").strip(), "usage": usage or {}}
    _append(rec)
    t = totals()
    return {"ok": True, "a": rec["a"], "ts": rec["ts"], "usage": rec["usage"],
            "tokens": t, "msg": "" if rec["a"] else "引擎没返回内容（可用性请看设置里的引擎状态）"}
