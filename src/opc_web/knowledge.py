# -*- coding: utf-8 -*-
"""知识库只读层：md 文件树与单文件读取（路径白名单约束；只读纪律在此强制）。"""
import datetime
import re

from . import config


def read_md(rel: str) -> str:
    """读取知识库 md（仅限权威根内 .md，防路径逃逸）。"""
    p = (config.ROOT / rel).resolve()
    if not str(p).startswith(str(config.ROOT.resolve())) or not p.is_file() or p.suffix != ".md":
        raise ValueError("非根目录范 md 文件")
    return config.read_text(p)


def _strip_front(text: str) -> str:
    """剥离顶层 YAML front-matter（--- … ---），让卡片摘要取到正文而不是元数据。"""
    if text.startswith("---\n") or text.startswith("---\r\n"):
        for sep in ("\n---\n", "\n---\r\n"):
            end = text.find(sep, 3)
            if end > 0:
                return text[end + len(sep):]
    return text


# OKF 知识型：每篇档案在 front-matter 里标注 type，卡片与检索按它分类。
OKF_LABELS = {"concept": "概念", "decision": "决策", "method": "方法",
              "data": "数据", "lesson": "教训", "problem": "问题"}
# 分类目录 → 默认知识型：老档案（规范文件、早期归档产物）没有 front-matter，
# 按所在分类推断一个，保证卡片上每篇都有型别可看。
CATEGORY_TYPE = {"OPC 规范": "concept", "产品": "concept", "技术": "concept",
                 "运营与增长": "concept", "用户与市场": "data", "方法": "method",
                 "数据": "data", "决策": "decision", "经验教训": "lesson"}


def front_meta(text: str) -> dict:
    """取最外层 front-matter 里的 OKF 元数据：type / created / updated / task / source。

    没有 front-matter 就返回空 dict（调用方按分类推断兜底）。"""
    if not text.startswith("---"):
        return {}
    nl = text.find(chr(10))
    if nl < 0:
        return {}
    end = text.find(chr(10) + "---", nl)
    if end < 0:
        return {}
    fm = text[nl + 1:end]
    out = {}
    for k in ("type", "created", "updated", "task", "source"):
        m = re.search(r"(?m)^%s:\s*(.+?)\s*$" % k, fm)
        if m:
            out[k] = m.group(1).strip().strip('"').strip("'")
    return out


def latest_daily() -> list:
    """返回《批阅台/每日简报-*.md》列表（按文件名日期降序，无日期兜底按修改时间）。"""
    d = config.BATCH_ROOT
    if not d.is_dir():
        return []
    items = []
    for p in d.glob("每日简报-*.md"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        items.append({"name": p.name, "rel": p.relative_to(config.ROOT).as_posix(),
                      "date": m.group(1) if m else "", "mtime": p.stat().st_mtime})
    items.sort(key=lambda x: (x["date"] or "", x["mtime"]), reverse=True)
    return items


def kb_entries() -> list:
    """知识库档案条目（卡片视角）：{rel, name, mtime, size, top, head}。
    知识库由老板助理（R1）统一管理、全体角色共同维护：角色产出先落工作区回报，
    经 R1 审核归档后进入《知识库/》，所有角色只读档案。"""
    out = []
    root = config.KB_ROOT
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*.md")):
        if "legacy" in p.parts or "归档" in p.parts or "archive" in p.parts:
            continue
        try:
            raw = config.read_text(p)
        except Exception:
            continue
        fm = front_meta(raw)   # 元数据从原文取（正文随后要剥掉 front-matter）
        t = _strip_front(raw)   # 摘要取正文，跳过 front-matter（okf 等档案的元数据不泄漏进卡片）
        body_lines = [ln.strip() for ln in t.split("\n") if ln.strip() and not ln.strip().startswith("#")]
        table_rows = [ln for ln in body_lines if ln.startswith("|")]
        head = []
        for ln in body_lines:
            if ln.startswith("|") or ln.startswith("---"):
                continue
            head.append(ln)
            if len(head) >= 3:
                break
        if head:
            htxt = " ".join(head)[:240]
        elif table_rows:
            htxt = "（表格档案：" + str(len(table_rows) - 1) + " 行）" + " " + (table_rows[0] if table_rows else "")
        else:
            htxt = "（档案以标题为主，点击卡片查看全文）"
        rel = p.relative_to(config.ROOT).as_posix()
        krel = p.relative_to(root).as_posix()
        # top 相对知识库根计算：根目录内平铺文件 top=""（不再产生占位分组头）；
        # 只有真正的子目录（如 知识库/档案/）才作为分组名。
        top = krel.split("/")[0] if "/" in krel else ""
        st = p.stat()
        # OKF 元数据：front-matter 优先，缺的按分类与文件时间兜底 —— 卡片上每篇都能看出
        # 「什么型的知识 / 什么时候建的 / 最近什么时候改的 / 从哪个任务沉淀来的」。
        day = datetime.date.fromtimestamp(st.st_mtime).isoformat()
        tp = str(fm.get("type") or "").strip().lower()
        if tp not in OKF_LABELS:
            tp = CATEGORY_TYPE.get(top, "concept")
        out.append({
            "rel": rel,
            "name": p.stem,
            "mtime": st.st_mtime,
            "size": st.st_size,
            "top": top,
            "head": htxt,
            "okf": tp,
            "okfLabel": OKF_LABELS[tp],
            "created": str(fm.get("created") or day)[:10],
            "updated": str(fm.get("updated") or day)[:10],
            "task": str(fm.get("task") or ""),
            "okfSource": "front-matter" if fm.get("type") else "按分类推断",
        })
    return out
