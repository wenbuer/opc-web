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

# 轻问答的工具轮数上限：够「读一两个文件再回答」，又不至于让输入无限膨胀。
# （api 引擎默认 40 步，那是给角色执行任务的；问答用不到，还容易烧钱。）
_MAX_STEPS = 6


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
        lines.append("- 知识库：%d 篇档案（清单如下，问「有没有 / 在哪篇」据此直接答，不必开文件）" % len(kb))
        # 把清单直接给出来：读一篇全文动辄一两千 token，而这份索引总共两百上下。
        # 索引常驻后，多数问题不用再靠工具去翻档案，也就不会把工具步数耗光。
        for ln in knowledge.index_lines():
            lines.append("  " + ln)
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


# 「预告」特征：模型只回一句准备动作就收尾（api 引擎把无工具调用的文本当成最终答复，
# 于是用户看到「思考中」半天，最后等来一句「我先看一下项目现状」而不是答案）。
_TEASE = ("我先", "我将", "让我", "接下来我", "先看", "先查", "先了解",
          "i'll", "let me", "i will", "i am going to")


def _looks_like_teaser(text: str) -> bool:
    """这条回答是不是「预告」而不是结论：空、极短且带准备动作的语气词。"""
    t = " ".join(str(text or "").split())
    if not t:
        return True
    if len(t) > 80:
        return False
    low = t.lower()
    return any(k in low for k in _TEASE)


def _merge_usage(u1, u2) -> dict:
    """两次调用的用量合并：重试也是真的花了，不能只记一次。"""
    out = dict(u1 or {})
    for k in ("inputTokens", "outputTokens", "cacheReadTokens", "reasoningTokens"):
        out[k] = int(out.get(k) or 0) + int((u2 or {}).get(k) or 0)
    return out


def _prompt(q: str) -> str:
    return (
        "你是 OPC 项目的老板助理 R1，现在和 R0（老板）做一次**临时答疑**。"
        + chr(10) + "硬性要求：" + chr(10)
        + "1. 直接给答案。**不许预告你打算做什么** —— 「我先看一下」「I'll check」这类准备动作"
        + "一律不算回答，用户读到的是空气；" + chr(10)
        + "2. 要文件内容就**立刻调用工具**去读，拿到结果再下结论，不许凭印象编；" + chr(10)
        + "3. 全程用**中文**回答；" + chr(10)
        + "4. 不要新建任务、不要派发角色、不要输出任务编号与流程话术；" + chr(10)
        + "5. 简短：先给结论，再补一两句依据；" + chr(10)
        + "6. 下面【项目现状】给了任务概况与知识库档案清单，用法分两种：" + chr(10)
        + "   · 「有哪些档案 / 在哪个分类 / 现在什么情况」—— 据此直接回答，不必开文件；" + chr(10)
        + "   · 只要问题涉及**正文写了什么**（某篇的结论、做法、口径），**必须用工具把那篇读出来再答**，"
        + "严禁凭标题推测内容；挑最相关的一两篇即可，别把工具步数耗光。" + chr(10) + chr(10)
        + "【项目现状】" + chr(10) + _context() + chr(10) + chr(10)
        + "【R0 的问题】" + chr(10) + q
    )


def ask(q: str, timeout: float = 240) -> dict:
    """问一句、答一句。不建任务、不派角色；用量记进临时会话账本。"""
    q = str(q or "").strip()
    if not q:
        return {"ok": False, "msg": "问题为空"}
    prompt = _prompt(q)
    text, usage = runner.run_headless_task(prompt, timeout=timeout, act="", purpose="prompt",
                                           max_steps=_MAX_STEPS)
    ans = (text or "").strip()
    if _looks_like_teaser(ans):
        # 只回了一句预告（或干脆没回）→ 追问一次，明确要求直接作答。
        # 两次的用量合并记账：重试同样烧了 token，不能只记一次。
        text2, usage2 = runner.run_headless_task(
            prompt + chr(10) + chr(10)
            + "（你上一次只回了一句准备动作，没有给出答案。这一次请直接作答："
            + "需要就用工具去查，然后把结论写出来，用中文。）",
            timeout=timeout, act="", purpose="prompt", max_steps=_MAX_STEPS)
        if (text2 or "").strip():
            ans = (text2 or "").strip()
        usage = _merge_usage(usage, usage2)
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "q": q, "a": ans, "usage": usage or {}}
    _append(rec)
    t = totals()
    return {"ok": True, "a": rec["a"], "ts": rec["ts"], "usage": rec["usage"],
            "tokens": t, "msg": "" if rec["a"] else "引擎没返回内容（可用性请看设置里的引擎状态）"}
