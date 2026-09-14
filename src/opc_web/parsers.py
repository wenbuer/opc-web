# -*- coding: utf-8 -*-
"""知识库 md 解析器：批阅台 / 角色架构 / 派发单 / 决策日志 / 时间线 / 任务清单。"""
import re

from . import store

# ---------- 批阅台 ----------
# 条目分两类：### 工作 N（例行进展，进「工作内容查看」）｜### 待决 N（R1 认为需 R0 拍板，进「决策裁决」）
HEAD_RE = re.compile(r"^###\s+待决\s+(\d+)\s*[｜|]\s*(.+)$")
HEAD_WORK_RE = re.compile(r"^###\s+工作\s+(\d+)\s*[｜|]\s*(.+)$")
JUDGE_RE = re.compile(r"^\s*-\s*\*\*[^：]*批阅[^：]*\*\*[:：]\s*(.*)$")
SECTION_RE = re.compile(r"^##\s+")


def _flush(cur, out):
    if cur is None:
        return
    item = {"n": cur["n"], "title": cur["title"], "lines": cur["lines"], "kind": cur["kind"]}
    if cur["judged"]:                       # 已有实质批阅/已阅 → 归档区
        out["archive"].append(item)
    elif cur["kind"] == "工作":             # 例行进展（无批阅栏）→ 工作内容
        out["work"].append(item)
    else:
        out["pending"].append(item)         # 待决未裁决 → 决策裁决


def parse_piyuetai(text: str) -> dict:
    """解析《批阅台/批阅台.md》 → {work:[例行进展], pending:[待决策], archive:[已批阅归档]}。"""
    lines = text.split("\n")
    out = {"work": [], "pending": [], "archive": []}
    cur = None
    for ln in lines:
        if SECTION_RE.match(ln):                     # 章节边界
            _flush(cur, out)
            cur = None
            continue
        m = HEAD_RE.match(ln)
        wm = HEAD_WORK_RE.match(ln) if not m else None
        if m or wm:
            _flush(cur, out)
            cur = {"n": int((m or wm).group(1)), "title": (m or wm).group(2).strip(),
                   "judged": False, "lines": [], "kind": "待决" if m else "工作"}
            continue
        if cur is not None:
            if ln.startswith("  ") and cur["lines"]:
                # 两空格缩进 = 上一字段值的续行（md 多行字段）：并入上一行，保留换行
                cur["lines"][-1] += "\n" + ln.strip()
                continue
            jm = JUDGE_RE.match(ln)
            if jm:
                val = jm.group(1).strip()
                if val and "待填" not in val:
                    cur["judged"] = True             # 已批阅/已阅：有实质内容
                cur["lines"].append(ln)              # 批阅行本身也保留 —— 决策归档要展示 裁决/意见
            elif ln.strip() and ln.strip() != "---":
                cur["lines"].append(ln)              # 收集背景/R 建议/需要拍板/进展
    _flush(cur, out)
    for bucket in (out["work"], out["pending"], out["archive"]):
        for it in bucket:
            it.pop("judged", None)
    return out


# ---------- 角色架构 ----------
def parse_roles() -> list:
    """角色清单（编号/名称/职责/状态/当前工作）。

    唯一权威 = 项目 agents/*.role.md（角色卡）；《知识库/OPC智能体角色架构.md》仅作人读速览，
    不作为功能入口（改删角色不再需要同步它）。R0 创始人无角色卡，固定前置行。
    状态只有两种：有未完成子任务 = 执行中，否则待命中；R0/R1 固定指挥中。"""
    from . import roles as _roles
    rows = [{"code": "R0", "name": "创始人", "duty": "总决策/批阅", "target": "—", "desc": "", "tags": ["决策"]}]
    for no, name in _roles.role_files():
        rows.append({"code": no, "name": name, "duty": _roles.role_duty(no), "target": "", "desc": "",
                     "tags": _roles.role_tags(no)})
    busy, latest_sub = set(), {}
    for p in store.subtasks():                 # 已按编号排序，后写覆盖 = 该角色最新的子任务
        if p["st"] in ("待派", "已派"):
            busy.add(p["role"])
        latest_sub[p["role"]] = p
    last_exec = store.last_execution_by_role()
    for it in rows:
        code = it["code"]
        it["status"] = "指挥中" if code in ("R0", "R1") else ("执行中" if code in busy else "待命中")
        e = last_exec.get(code)
        if e and e.get("sub"):                 # 最近一次执行：执行中=正在做的，待命中=上次做的
            it["current"] = (e["sub_no"].rsplit("-S", 1)[0] if "-S" in e["sub_no"] else e["sub_no"])
        elif code in latest_sub:               # 无执行记录 → 退到最新子任务
            it["current"] = latest_sub[code]["taskNo"]
        else:
            it["current"] = "无"
    return rows



