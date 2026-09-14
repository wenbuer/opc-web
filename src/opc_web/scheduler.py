# -*- coding: utf-8 -*-
"""调度中枢 v1.15：subagent 化 + 名称工作区 + SQLite 台账。

执行模型：常驻会话主 agent（R1 助理）是唯一执行方 —— 控制台只负责把
「R0 指令」落成台账（store.py）并把「待执行指令」记入调度日志；
R1 主会话读取台账后用 DSH subagent 体系向下派活，子 agent 产出
《工作区/<角色名称>/T-xxx-Sn.md》，控制台归档时摄取入库。

v1.15：任务/子任务/回报三张表由 SQLite 承载，md 只留正文与公文。
原先「R1 手写 md 表格行 → 程序原样字符串搬运」的 r1_apply 通道已删除。
"""
import datetime
import json
import re
import subprocess
import threading
import time

from . import agent, config, knowledge, runner, store, templates


def _wb_role_dirs():
    """《工作区/》下所有角色输出目录（按角色名称命名）。"""
    wb = config.WORKSPACE_ROOT
    if not wb.is_dir():
        return []
    return sorted(d for d in wb.iterdir() if d.is_dir())


SCHED_LOCK = threading.Lock()
SCHED_STATE = {"busy": False, "tag": "", "lastOk": None, "paused": False}


def plan_execute() -> dict:
    """按台账里的待派/已派子任务，逐行生成 subagent 派发指令（由主会话 R1 逐个派发）。"""
    rows = [r for r in store.subtasks() if r["st"] in ("", "待派", "已派")]
    if not rows:
        return {"issued": [], "total": len(store.subtasks()), "msg": "无待派子任务"}
    spec_lines = []
    for r in rows:
        spec = agent.subtask_spec(r["role"], "执行子任务：%s。期望产出：%s。" % (r["sub"], r["expect"]),
                                  expect=r["expect"], sub_no=r["no"])
        spec_lines.append("- %s → %s %s：%s" % (r["no"], r["role"], spec["roleName"], spec["output"]))
    agent.log_schedule("派发单执行指令", "【待常驻主会话 R1 按台账逐行 subagent 派发】\n" + "\n".join(spec_lines))
    return {"issued": [r["no"] + "→" + r["role"] for r in rows], "total": len(store.subtasks())}


def scan_once():
    """一轮调度扫描：台账有待派任务 → 立即启动自动执行链。"""
    try:
        if SCHED_STATE.get("paused") or SCHED_STATE.get("busy"):
            return
        for t in store.tasks():
            if t["status"] == "待派":
                from . import chain
                threading.Thread(target=chain.execute, args=(t["no"], t["task"]), daemon=True).start()
                return
    except Exception:
        pass


def schedule_once():
    """定时任务触发检查：到期任务 → 落台账 + 调度日志。"""
    try:
        now = datetime.datetime.now()
        jobs = config.load_schedules()
        changed = False
        for j in jobs:
            if not j.get("enabled", True):
                continue
            nxt = config.schedule_next(j, now)
            if nxt is None or nxt > now:
                continue
            task = str(j.get("task") or "").strip() or "定时任务"
            no = store.add_task(task, "定时任务（R1 执行）")
            j["lastRun"] = now.strftime("%Y-%m-%d %H:%M:%S")
            agent.log_schedule("定时任务 %s" % (j.get("id") or "?"),
                               "【定时任务到期】%s → 已下达 %s 待常驻主会话 R1 执行：%s"
                               % (j.get("id") or "?", no, task))
            changed = True
        if changed:
            config.save_schedules(jobs)
    except Exception:
        pass


def _git_snapshot(reason: str):
    """keeptalk 运行数据自动 git 快照：无变更 / 非仓库 / git 不可用 → 静默跳过。

    09-09 两次数据误删事故（15:06、16:08）的教训：运行数据必须随业务变化
    持续入库，误删才能无损找回——git 快照是唯一可靠的兜底。"""
    try:
        if not (config.ROOT / ".git").is_dir():
            return
        def _run(args):
            return subprocess.run(["git", "-C", str(config.ROOT)] + args,
                                  capture_output=True, timeout=60)
        if _run(["add", "-A"]).returncode != 0:
            return
        if not _run(["status", "--short"]).stdout.strip():
            return                       # 无变更不空提交
        _run(["commit", "-m", "自动快照: " + reason])
    except Exception:
        pass


_SNAPSHOT_EVERY = 5              # auto_pilot 每 N 轮做一次数据快照（pollSeconds 默认 8 秒 ≈ 40 秒）


def auto_pilot():
    """常驻调度守护：轮询台账 + 定时任务触发检查 + 自动归档 + 数据自动快照；
    有待派任务即启动自动执行链，子任务完结后自动归档（无需手动点「归档」）。
    轮询间隔见 opc-config.json 的 pollSeconds（默认 8 秒，手改即时生效）。"""
    _tick = 0
    while True:
        time.sleep(config.tune("pollSeconds"))
        schedule_once()
        scan_once()
        archive_once()
        _tick = (_tick + 1) % _SNAPSHOT_EVERY
        if _tick == 0:
            _git_snapshot("调度轮询")


def _title_of(text: str, fallback: str) -> str:
    m = re.search(r"^#\s*(.+)$", text, re.M)
    return (m.group(1).strip() if m else fallback)[:70]


def r1_archive() -> dict:
    """归档：扫各角色工作区的 .meta.json → 已完成的子任务入库 → 正文移入 已归档/。

    幂等由主键（子任务编号）保证：重复归档即覆盖同一行，不再靠整行字符串比对去重。
    文件在=待处理、文件移走=已处理，文件系统本身就是状态机。"""
    done, skipped, ledger = [], [], []
    for d in _wb_role_dirs():
        for meta_p in sorted(d.glob("*.meta.json")):
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
            except Exception as e:
                ledger.append("%s（元数据损坏：%s）" % (meta_p.name, str(e)[:40]))
                continue
            sub_no = str(meta.get("subNo") or meta_p.stem.replace(".meta", ""))
            status = str(meta.get("status") or "待执行").strip()
            body_p = d / (sub_no + "-report.md")          # 新命名：完成回报
            if not body_p.exists():
                body_p = d / (sub_no + ".md")             # 兼容历史旧命名
            if status in ("待执行", "执行中") or not body_p.exists():
                skipped.append("%s（%s）" % (sub_no, status if body_p.exists() else "正文未产出"))
                continue
            text = config.read_text(body_p)
            # 产出生命周期（模型 A）：工作中 = -report（完成回报）；归档时改名为 -output.md 移入 已归档/
            arc = d / "已归档"
            arc.mkdir(exist_ok=True)
            stem = body_p.stem
            if stem.endswith("-report"):
                stem = stem[: -len("-report")]
            out_name = stem + "-output.md"
            arc_rel = (arc / out_name).relative_to(config.ROOT).as_posix()
            store.put_report(sub_no, str(meta.get("taskNo") or ""), str(meta.get("role") or ""),
                             status, _title_of(text, sub_no), text, arc_rel)
            store.set_subtask(sub_no, status)
            store.settle_execution(sub_no, status)
            body_p.replace(arc / out_name)
            meta_p.replace(arc / meta_p.name)
            done.append("%s → 回报入库（%s）" % (sub_no, status))
        # 内容类交付物（非子任务产出）：不猜落库路径，登记待 R1/R0 指定
        for f in sorted(d.glob("*.md")):
            if (d / (f.stem + ".meta.json")).exists():
                continue
            ledger.append(f.relative_to(config.WORKSPACE_ROOT).as_posix())
    # 任务级回填：子任务全部完成 → 任务完成
    by_task = {}
    for s in store.subtasks():
        by_task.setdefault(s["taskNo"], []).append(s["st"])
    for task_no, sts in by_task.items():
        if sts and all(x == "完成" for x in sts):
            store.set_task(task_no, "完成", "%d/%d 子任务完成" % (len(sts), len(sts)))
            done.append("%s → 任务完成" % task_no)
    out = {"archived": done, "skipped": skipped, "ledger": ledger}
    if done:
        agent.log_schedule("R1 自动归档",
                           "子任务已全部/部分完结，自动归档入库 %d 项：%s" % (len(done), "；".join(done)))
    if ledger:
        lg = config.BATCH_ROOT / ("归档登记-" + datetime.date.today().isoformat() + ".md")
        lg.parent.mkdir(parents=True, exist_ok=True)
        with open(lg, "a", encoding="utf-8") as fh:
            fh.write("\n".join("- " + p for p in ledger) + "\n")
    return out


def archive_once():
    """自动归档（R1 中枢守护）：扫描工作区，出现已完结（完成/部分/阻塞）子任务即归档一次。
    幂等由 r1_archive 保证：重复扫描/重复调用不会重复入库；执行中的子任务跳过。"""
    try:
        for d in _wb_role_dirs():
            for meta_p in d.glob("*.meta.json"):
                try:
                    st = str(json.loads(meta_p.read_text(encoding="utf-8")).get("status") or "").strip()
                except Exception:
                    continue
                if st in ("完成", "部分", "阻塞"):
                    r1_archive()
                    _git_snapshot("归档入库")
                    return
    except Exception:
        pass


def _piyue_next_no(text: str) -> int:
    # 工作条目与待决条目共用递增编号，避免跨区重号
    nums = [int(m) for m in re.findall(r"^###\s+(?:待决|工作)\s+(\d+)", text, re.M)]
    return (max(nums) + 1) if nums else 1


# 「该不该进决策裁决」的唯一判据：角色在回报里按模板的「准入清单」自己声明。
# 早先用宽关键词（「是否 / 决定 / 方向 / 启动」）判——回报里到处都有这些词，
# 例行汇报被整片推成待决；改扫「需要拍板」字样又会把角色正文的泛指句子抓成声明
# （T-007 把 UI 描述当成待拍板内容）。所以只认这个小节，别的都不算。
_PENDING_HEAD = re.compile(r"(?m)^#{2,3}\s*需要\s*R0\s*拍板")


def _field_lines(key: str, value: str) -> list:
    """条目字段 → 行列表：首行 `- **key**：首段`，其余段以两空格缩进续行（md 人读清晰、解析可还原换行）。"""
    parts = str(value or "").split("\n")
    first = parts[0].strip()
    out = ["- **" + key + "**：" + first] if first else ["- **" + key + "**："]
    for ln in parts[1:]:
        s = ln.strip()
        if s:
            out.append("  " + s)
    return out


def _pending_items(reps) -> str:
    """回报里「## 需要 R0 拍板」小节的实质内容（多角色拼接）。

    这是**唯一**的「该进决策裁决」判据：角色按《模板-回报产出》的准入清单（方向取舍 /
    花钱对外 / 例外授权 / 验收定稿，每任务最多 2 条）自行声明；没写这节或写「无」即例行汇报。
    返回空串表示无待拍板事项。"""
    out = []
    for r in reps or []:
        body = str((r or {}).get("body") or "")
        m = _PENDING_HEAD.search(body)
        if not m:
            continue
        seg = body[m.end():]
        nxt = re.search(r"(?m)^##\s", seg)
        if nxt:
            seg = seg[:nxt.start()]
        seg = seg.strip()
        if len(seg) > 8 and seg.replace("。", "").strip() not in ("无", "没有", "暂无"):
            out.append("【%s】\n%s" % ((r or {}).get("role") or "?", seg))
    return "\n\n".join(out)


def _tree_text(root, max_depth=3):
    """文本目录树（剔除运行数据/依赖目录），用于代码类工作汇总展示当前目录结构。"""
    skip = {".git", "node_modules", "__pycache__", ".dsh-tmp", "已归档"}
    out = []
    def walk(p, pre, dep):
        if dep > max_depth:
            return
        try:
            ents = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except OSError:
            return
        files = [e for e in ents if not e.is_dir() and e.name not in skip and not e.name.endswith((".pyc", ".db", ".db-journal"))]
        dirs = [e for e in ents if e.is_dir() and e.name not in skip]
        for i, d in enumerate(dirs):
            last = (i == len(dirs) - 1) and not files
            out.append(pre + ("└── " if last else "├── ") + d.name + "/")
            walk(d, pre + ("    " if last else "│   "), dep + 1)
        for j, f in enumerate(files):
            out.append(pre + ("└── " if j == len(files) - 1 else "├── ") + f.name)
    root = config.ROOT
    out.append(root.name + "/")
    walk(root, "", 1)
    return "\n".join(out[:160])


_TRIPLE_BT = chr(96) * 3      # ```（源码避免反引号字面）
_CODE_HINT = (".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".html", ".htm", ".vue", ".sql", ".json")


def _looks_code(text: str, src: str) -> bool:
    """启发式：产出正文含代码块/程序特征，或产出文件为代码文件 → 代码类工作。"""
    if src and src.lower().endswith(_CODE_HINT):
        return True
    if _TRIPLE_BT in (text or ""):
        return True
    head = (text or "")[:3000]
    for pat in ("def ", "function ", "class ", "import ", "const ", "let ", "interface ", "CREATE TABLE", "<!DOCTYPE", "#include"):
        if pat in head:
            return True
    return False


def _digest_body(text: str, limit: int = 600) -> str:
    """抽取产出要点：去掉控制台预置模板头，保留原始 md（标题/加粗/换行），超长截断。"""
    t = (text or "").strip()
    idx = t.find("\n---\n")                 # 预置模板头以 --- 分隔线结束
    if 0 < idx < 1200:
        t = t[idx + 6:].lstrip("\n")
    t = t.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return ""
    t = re.sub(r"\n{3,}", "\n\n", t)       # 压缩多余空行，保留段落换行
    if len(t) > limit:
        t = t[:limit].rstrip() + "\n\n……（过长截断，完整见「查看角色产物」）"
    return t


def _one_line_digest(text: str, limit: int = 120) -> str:
    """把产出压成「一段话」摘要（剥掉 md 标记），给任务信息里的「回报摘要」字段用。"""
    t = _digest_body(text, limit=3000)
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"\[[xX]\]\s*", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", "\1", t)
    t = t.replace("**", " ").replace("`", " ").replace("#", " ").replace("*", " ")
    t = re.sub(r"^[\s>|-]+", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    return (t[:limit] + "…") if len(t) > limit else t


# 「需要 R0 拍板」小节里常见的流程/机制套话（本身不含任何具体待决内容），抽取时剔除：
# 例：“任务含决策信号（定价 / 方向 / 是否推进等），请 R0 裁决；驳回 / 修改意见将触发重新派发。”
# 这类话等于没写 —— R0 要看到的是“现状背景 → 可选方案 → 建议 → 具体请拍板什么”。
_DECISION_NOISE = ("决策信号", "请 R0 裁决", "请R0裁决", "R0 裁决", "请 R0 拍板", "请R0拍板",
                   "驳回", "重新派发", "修改意见", "回报未列出", "请展开本条目", "请直接批复",
                   "完整产出后再给出意见", "读完完整产出后再给出意见")
_DECISION_CONCRETE = ("方案", "还是", "或", "建议", "选择", "采用", "预算", "上限", "金额", "？", "?")


def _clean_decision_seg(role: str, seg: str) -> str:
    """把某角色「需要 R0 拍板」原文里的机制套话句剔除，只留具体待决内容（过短视为没写）。"""
    t = (seg or "").strip()
    t = re.sub(r"^[#\-*\s]*" +
               r"(?:需要\s*R0\s*拍板|需要R0拍板|需要拍板|待拍板|请\s*R0\s*拍板|请R0拍板|需\s*R0\s*决策|请求\s*R0\s*决策)" +
               r"[\s:：]*", "", t)
    frags = [f.strip(" \t·-*#") for f in re.split(r"(?<=[。！？!?；;])|[\n\r]", t)]
    keep = []
    for f in frags:
        if not f:
            continue
        noise = any(w in f for w in _DECISION_NOISE)
        concrete = any(w in f for w in _DECISION_CONCRETE) or bool(re.search(r"(?<![A-Za-zRr])[0-9０-９]", f))
        if noise and not concrete:
            continue          # 纯机制套话，不等于要拍板的具体内容
        keep.append(f)
    cleaned = "\n".join(keep).strip()
    return cleaned if len(cleaned) >= 20 else ""


def _decision_items(reps: list) -> str:
    """从各角色回报正文抽取「需要 R0 拍板」具体内容 → 拼接为待决条目字段值（无则空串）。

    子 agent 按约定写「## 需要 R0 拍板」小节（或内联“需要 R0 拍板：…”）；
    这里取首个命中位置起 700 字内、到下一个二级标题前的原文，剔除“请 R0 裁决 / 驳回将
    重新派发”这类机制空话后，R0 拍板看的就是它。"""
    out = []
    marks = ("需要 R0 拍板", "需要R0拍板", "需要拍板", "待拍板",
             "请 R0 拍板", "请R0拍板", "需 R0 决策", "请求 R0 决策")
    for role, body in (reps or []):
        t = str(body or "")
        pos = min([i for mk in marks if (i := t.find(mk)) >= 0] or [-1])
        if pos < 0:
            continue
        seg = t[pos:pos + 700]
        cut = seg.find("\n## ")
        if cut > 0:
            seg = seg[:cut]
        seg = _clean_decision_seg(role, seg)
        if seg:
            out.append(("【%s】\n" % (role or "")) + seg)
    return "\n\n".join(out)


def work_summary(task_no: str) -> str:
    """R1 汇总任务全部 subagent 产出 →《工作区/老板助理/T-xxx-工作汇总.md》。

    内容：各角色工作与产出全文；代码类工作附「改动/产出文件 + 当前目录结构」。
    返回 rel（供工作内容条目挂载，UI 直接查看）；失败返回 None。"""
    try:
        reps = store.reports(task_no)
        if not reps:
            return None
        task_row = None
        for t in store.tasks():
            if t["no"] == task_no:
                task_row = t
                break
        subs = {}
        try:
            for s in store.subtasks(task_no):
                subs[s["no"]] = s["sub"]
        except Exception:
            pass
        today = datetime.date.today().isoformat()
        lines = ["# %s 工作汇总（R1） · %s" % (task_no, today), ""]
        lines.append("> 任务：" + ((task_row or {}).get("task") or "").replace("\n", " ")[:300])
        lines.append("> 本文件由 R1 汇总 %d 个 subagent 的回报与产出，供 R0 直接查看。" % len(reps))
        has_code = False
        code_files = []
        for r in reps:
            role = str(r.get("role") or "?")
            st = str(r.get("status") or "")
            sub = subs.get(str(r.get("sub_no") or ""), "")
            src = str(r.get("src") or "")
            body = str(r.get("body") or "")
            lines.append("")
            lines.append("## " + role + "（" + st + "）")
            if sub:
                lines.append("> 子任务：" + sub.replace("\n", " ")[:200])
            full = _digest_body(body, limit=30000)   # R1 汇总报告 = 完整产出（去模板头、不截断）
            if full:
                lines.append("")
                lines.append(full)
            if src:
                lines.append("")
                lines.append("> 产出文件：" + src)
            if _looks_code(body, src):
                has_code = True
                code_files.append(src)
        if has_code:
            lines.append("")
            lines.append("## 代码工作：改动与当前目录结构")
            lines.append("**改动/产出文件**：" + ("；".join(f for f in code_files if f) or "见各子任务产出"))
            lines.append("")
            lines.append("**当前目录结构**（项目根，" + config.ROOT.name + "）：")
            lines.append("")
            lines.append(_TRIPLE_BT)
            lines.append(_tree_text(config.ROOT))
            lines.append(_TRIPLE_BT)
        out_p = config.WORKSPACE_ROOT / config.role_dir("R1") / (task_no + "-summary.md")
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text("\n".join(lines), encoding="utf-8")
        return out_p.relative_to(config.ROOT).as_posix()
    except Exception:
        return None



def _headless_text(prompt: str, timeout: float = 600) -> str:
    """尝试用 dsh headless 让 R1 做文本类收尾（汇总/抽取）；失败返回空串。"""
    try:
        text, _ = runner.run_headless_task(prompt, timeout, purpose="prompt")
        return (text or "").strip()
    except Exception:
        return ""

def _digest_reps(reps, limit: int = 900) -> str:
    """回报正文 → 单行摘要（供模型汇总/抽取，控制长度）。"""
    out = []
    for r in reps:
        body = str(r.get("body") or "").strip()
        one = re.sub(r"[ \t]+", " ", body)[:limit]
        out.append("【%s｜%s】（%s）：%s" % (r.get("task_no") or "?", r.get("role") or "?", r.get("status") or "?", one))
    return "\n".join(out)

_DAILY_TASK_SECTION = "## 完成任务"
_TASK_HEAD_RE = re.compile(r"^-\s+(T-[0-9A-Za-z-]+)\s*[｜|]")


def _daily_task_blocks(text: str) -> dict:
    """简报文本 -> {任务号: 清单行}（「## 完成任务」节里的「- T-xxx｜一句话」）。"""
    blocks = {}
    m = re.search(r"^" + re.escape(_DAILY_TASK_SECTION) + r"\s*$", text, re.M)
    if not m:
        return blocks
    seg = text[m.end():]
    nxt = re.search(r"^## ", seg, re.M)
    if nxt:
        seg = seg[:nxt.start()]
    for ln in seg.split(chr(10)):
        hm = _TASK_HEAD_RE.match(ln.strip())
        if hm:
            blocks[hm.group(1)] = ln.strip()
    return blocks


def _merge_daily(old_text: str, new_text: str, task_no: str) -> str:
    """模型合并稿的校验：旧稿出现过的任务号，新稿必须一个不少。

    不再要求逐字保留旧段落——那会让简报只增不减（历史简报曾膨胀到 51 KB，
    每条任务都带着执行细节滚下去）。现在允许压缩改写，只守住「任务不丢」；
    缺任务号 → 返回 ""，调用方走代码级合并。"""
    old_blocks = _daily_task_blocks(old_text)
    new_blocks = _daily_task_blocks(new_text)
    missing = [tno for tno in old_blocks if tno not in new_blocks]
    if missing:
        return ""
    return new_text


def _insert_into_section(text: str, section: str, block: str) -> str:
    """把 block 插到 text 中 section 节的末尾（下一个 ## 标题之前）；无该节则追加文尾。"""
    m = re.search(r"^" + re.escape(section) + r"\s*$", text, re.M)
    if not m:
        return text.rstrip() + "\n\n" + section + "\n\n" + block + "\n"
    seg_start = m.end()
    nxt = re.search(r"^## ", text[seg_start:], re.M)
    end = seg_start + nxt.start() if nxt else len(text)
    body = text[seg_start:end].rstrip("\n")
    new_seg = (body + "\n\n" + block + "\n\n") if body else ("\n" + block + "\n\n")
    return text[:seg_start] + new_seg + text[end:].lstrip("\n")


def _daily_fallback(old_text: str, reps: list, task_no: str, datestr: str) -> str:
    """模型不可用时的代码级合并：每个任务压成一行插进「完成任务」清单，其余内容不动。"""
    tnos = sorted({str(r.get("task_no") or "T-?") for r in reps})
    roles = "、".join(sorted({str(r.get("role") or "?") for r in reps}))
    lines = []
    for tno in tnos:
        rs = [r for r in reps if str(r.get("task_no") or "") == tno]
        one = _one_line_digest(str(rs[0].get("body") or ""), limit=60) if rs else ""
        lines.append("- %s｜%s（%s）" % (tno, one or "已完成并归档", roles))
    if not old_text.strip():
        return chr(10).join([
            "# 每日简报 · " + datestr, "",
            "## 今天干了什么",
            "_模型收尾不可用，本节为代码级降级合并：今日完成 " + "、".join(tnos) + "。_", "",
            _DAILY_TASK_SECTION] + lines + [
            "", "## 待 R0 拍板", "无", "",
            "## 风险与待办", "**风险**：无", "**待办**：无", ""])
    text = old_text.rstrip() + chr(10)
    blocks = _daily_task_blocks(text)
    rest = []
    for tno, ln in zip(tnos, lines):
        if tno in blocks:
            text = text.replace(blocks[tno], ln)          # 同任务重跑：更新那一行
        else:
            rest.append(ln)
    if rest:
        text = _insert_into_section(text, _DAILY_TASK_SECTION, chr(10).join(rest))
    return text


def build_daily_report(task_no: str = None, datestr: str = None) -> dict:
    """任务执行链结束后：把该任务的总结合并进《批阅台/每日简报-<date>.md》（增量合并，非全量重写）。

    - 当天首份 → 模型按《模板-每日简报》生成完整简报；
    - 已有简报 → 模型输出合并稿，代码强制校验（_merge_daily）：除本次任务外，已有任务段落
      必须逐字保留，防止盲目追加 / 改写历史；校验不过或模型不可用 → 代码级合并
      （_daily_fallback，只插本任务段落与概况一行，其余不动）。
    当天无本次任务回报则跳过。"""
    datestr = datestr or datetime.date.today().isoformat()
    try:
        all_reps = store.reports(task_no) if task_no else store.reports()
        reps = [r for r in all_reps if (r.get("date") or "") == datestr]
    except Exception:
        reps = []
    if not reps:
        return {"ok": True, "merged": False, "msg": "当日无任务回报，不更新简报"}
    target = config.BATCH_ROOT / ("每日简报-%s.md" % datestr)
    target.parent.mkdir(parents=True, exist_ok=True)
    old_text = config.read_text(target) if target.exists() else ""
    digest = _digest_reps(reps, limit=2400)
    has_old = bool(old_text.strip())
    prompt = (
        "你是老板助理 R1。请按《模板-每日简报》把任务 %s 的回报%s每日简报：\n"
        "- %s。输出合并后的完整简报 markdown（# 每日简报 · %s 标题 + 今天干了什么 / "
        "完成任务 / 待 R0 拍板 / 风险与待办 四节）。\n"
        "纪律——简洁优先：「今天干了什么」2~4 句讲清主线；「完成任务」每个任务只占一行（≤40 字）；\n"
        "待拍板只列「决策点标题 + 对应待决编号」；风险与待办各不超过 3 条；全篇 ≤ 50 行。\n"
        "禁止搬运回报原文、罗列文件路径 / 测试项数 / 自检项数 / git 快照号 / 沙箱限制；\n"
        "已有任务的旧细节可以大幅压缩（只要任务号仍出现在「完成任务」节即可），本次任务也在同一行内收口。\n"
        "结尾禁止对话性收尾。\n\n"
        "《模板-每日简报》：\n%s\n\n现有简报：\n%s\n\n本次任务回报：\n%s"
        % (task_no or "（当日全部）",
           ("增量合并进" if has_old else "生成当天首份"),
           ("已有简报 → 按上面纪律重写为简洁版" if has_old else "当天尚无简报 → 全新生成"),
           datestr,
           templates.doc_template("每日简报"),
           old_text.strip() or "（当天尚无简报）", digest))
    text = _headless_text(prompt, 600)
    if text and has_old:
        text = _merge_daily(old_text, text.strip(), task_no or "")   # 校验失败返回 "" → 走降级合并
    if not text or not text.strip():
        text = _daily_fallback(old_text, reps, task_no, datestr)
    target.write_text(text.strip() + "\n", encoding="utf-8")
    return {"ok": True, "merged": has_old, "file": target.name,
            "rel": target.relative_to(config.ROOT).as_posix()}

def _kb_skim() -> str:
    """知识库已有档案简表（按分类）：让 R1 知道该 create 还是 merge（不重复沉淀）。"""
    out = []
    for cat in config.KB_CATEGORIES:
        d = config.KB_ROOT / cat
        if not d.is_dir():
            continue
        files = [p.stem for p in sorted(d.glob("*.md"))]
        if files:
            out.append("%s：%s" % (cat, "、".join(files[:20])))
    return "\n".join(out) if out else "（知识库暂未分类，各主题为空）"


def _parse_kb_digest(text):
    """解析 R1 的沉淀决策 JSON（容忍 json 代码块包裹 / 前后杂字）。"""
    t = re.sub(_TRIPLE_BT + r"(?:json)?", "", (text or ""), flags=re.I).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        obj = json.loads(t[i:j + 1])
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _slug_title(title: str) -> str:
    """档案标题 → 安全文件名（保留中文/字母数字，去非法字符）。"""
    return config.sanitize_dir(title) or "沉淀"


def kb_digest(task_no: str) -> dict:
    """R1 判断是否沉淀知识到知识库：按主题分类，有价值才入库；同主题有相关档案则合并补充。

    - 不再每任务都生成 <任务号>-okf.md：R1 先判价值（none→跳过），再归类（create / merge）。
    - 分类目录 = config.KB_CATEGORIES；文件名用语义化标题；OKF 只是每篇的知识型(type)标注。"""
    reps = store.reports(task_no)
    if not reps:
        return {"ok": True, "created": False, "msg": "该任务无回报，跳过知识沉淀"}
    digest = _digest_reps(reps, limit=1200)
    skim = _kb_skim()
    prompt = (
        "你是老板助理 R1，负责知识库沉淀。请判断本次任务产出里有没有值得沉淀到知识库的知识，并归类。\n"
        "知识库按主题分类，已有档案如下：\n%s\n\n"
        "只沉淀真正有价值、可复用的知识（结论 / 方法 / 数据 / 教训 / 决策）；"
        "流水账、一次性过程记录、只是把回报换个说法，都不要沉淀。\n"
        "归类硬规则：type=lesson 的教训一律归「经验教训」分类，标题用「教训-<一句话结论>」格式；"
        "type=decision 归「决策」，type=method 归「方法」，type=data 归「数据」。\n"
        "输出 JSON（不要多余文字，body 用简洁 markdown）：\n"
        '{"action":"none|create|merge","category":"<分类名，取自上面主题列表>",'
        '"title":"<档案标题(≤40字)>","type":"concept|decision|method|data|lesson|problem",'
        '"body":"<markdown 正文>","merge_target":"<merge 时填已存在文件名，create 留空>"}\n'
        "规则：action=none 无可沉淀知识；action=create 有知识且该分类无相关档案；"
        "action=merge 该分类已有相关档案（merge_target 填已有文件名，body 给合并后的完整正文）。\n\n"
        "任务 %s 回报：\n%s" % (skim, task_no, digest))
    text = _headless_text(prompt, 600)
    if not text:
        return {"ok": True, "created": False, "msg": "模型未返回，未沉淀"}
    d = _parse_kb_digest(text)
    if not d:
        return {"ok": True, "created": False, "msg": "沉淀决策解析失败，未入库"}
    action = str(d.get("action") or "").strip()
    if action not in ("create", "merge"):
        return {"ok": True, "created": False, "msg": "R1 判定无可沉淀知识，未入库"}
    cat = str(d.get("category") or "").strip()
    if cat not in config.KB_CATEGORIES:
        return {"ok": True, "created": False, "msg": "分类「%s」不在知识库分类里，未入库" % cat}
    title = str(d.get("title") or "").strip()[:40] or ("%s 沉淀" % task_no)
    body = str(d.get("body") or "").strip()
    if not body:
        return {"ok": True, "created": False, "msg": "正文为空，未入库"}
    catdir = config.KB_ROOT / cat
    catdir.mkdir(parents=True, exist_ok=True)
    target = catdir / (_slug_title(title) + ".md")
    if action == "merge":
        mt = str(d.get("merge_target") or "").strip()
        cand = None
        if mt:
            cand = catdir / (mt if mt.endswith(".md") else mt + ".md")
        cand = cand if (cand is not None and cand.is_file()) else target
        target = cand if cand.is_file() else target
    # OKF 知识型标注落盘：front-matter 记录 type（concept/decision/method/data/lesson/problem），
    # knowledge._strip_front / _strip_okf_frontmatter 读取时会剥离，不影响正文渲染，供后续按知识型细分统计。
    _kb_types = {"concept", "decision", "method", "data", "lesson", "problem"}
    _tp = str(d.get("type") or "concept").strip().lower()
    if _tp not in _kb_types:
        _tp = "concept"
    # merge 到已有档案时沿用它的建档时间，只把 updated 与来源任务刷成本次的
    today = datetime.date.today().isoformat()
    old = {}
    if action == "merge" and target.is_file():
        try:
            old = knowledge.front_meta(target.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    front = ("---\ntype: %s\ncreated: %s\nupdated: %s\ntask: %s\n---\n"
             % (_tp, old.get("created") or today, today, task_no))
    target.write_text(front + body.strip() + "\n", encoding="utf-8")
    rel = target.relative_to(config.ROOT).as_posix()
    return {"ok": True, "created": True, "action": action, "rel": rel,
            "msg": ("已合并补充到知识库「%s/%s」" % (cat, target.name)) if action == "merge"
                   else ("已沉淀到知识库「%s/%s」" % (cat, target.name))}

def _advice_summary(reps, task_text: str) -> str:
    """R1 按《模板-决策建议》把角色声明的待拍板事项提炼成「决策建议」栏正文。

    只在 _pending_items 非空（确有需 R0 定的事项）时才被调用；模型不可用返回 "" 由调用方回退。"""
    if not reps and not task_text:
        return ""
    digest = _digest_reps(reps, limit=2400) if reps else str(task_text or "")[:1600]
    # _decision_items 收的是 (role, body) 元组列表；直接传整条记录会当场 ValueError
    # （too many values to unpack），被上层 except 吞掉后永远走回退摘要 —— 「决策建议没按模板走」即此因。
    ask = _decision_items([(r.get("role"), r.get("body")) for r in reps]) if reps else ""
    prompt = (
        "你是老板助理 R1。请按《模板-决策建议》为批阅台待决条目写「决策建议」栏："
        "依次含小节 决策点（一句话问句）/ 现状背景（2~4 句）/ 建议（明确选哪个 + 一两句理由；"
        "无可拍板事项就给下一步动作建议）/ 拍板后动作（批准/驳回/修改后 R1 分别怎么转）/ 附注（可省略）。\n"
        "要求：完整、像人话，不搬运回报原文的零碎句，不写机制套话；**只围绕角色在"
        "「需要 R0 拍板」小节里声明的事项提炼**，不要扩散到任务的其他部分。\n"
        "只输出「决策建议」栏正文（各小节），不要多余解释。\n\n"
        "《模板-决策建议》：\n%s\n\n任务原文：%s\n\n各角色回报：\n%s\n\n各角色「需要 R0 拍板」原文：\n%s"
        % (templates.doc_template("决策建议"), str(task_text or "")[:900], digest, ask or "（无）"))
    text = _headless_text(prompt, 600)
    return (text or "").strip()


def decision_context(task_text: str, limit: int = 2400) -> str:
    """从任务文本提取「待决 #N」引用 → 读批阅台对应条目的「决策建议」全文。

    R0 批阅意见往往只有一句（如「先实现A吧」），方案 A 的定义在待决条目的
    「决策建议」栏里 —— 拆解器与执行角色都必须拿到它，否则只能望文生义
    （T-006 事故：拆解器在不知道方案 A 是什么的情况下瞎编了子任务）。
    找不到引用 / 条目 / 字段返回 ""。"""
    m = re.search(r"待决\s*#?\s*(\d+)", task_text or "")
    if not m:
        return ""
    try:
        p = config.ROOT / config.PIYUETAI_REL
        text = config.read_text(p) if p.exists() else ""
    except Exception:
        return ""
    mm = re.search(r"^###\s+待决\s+%s\s*[｜|][^\n]*$" % m.group(1), text, re.M)
    if not mm:
        return ""
    seg = text[mm.end():]
    nxt = re.search(r"^###\s", seg, re.M)
    if nxt:
        seg = seg[:nxt.start()]
    vals, grab = [], False
    for ln in seg.split("\n"):
        if ln.startswith("- **决策建议**："):
            grab = True
            vals.append(ln[len("- **决策建议**："):].strip())
            continue
        if grab:
            if ln.startswith("  ") and ln.strip():
                vals.append(ln.strip())
            elif ln.startswith(("- **", "### ")):
                break
    out = "\n".join(v for v in vals if v).strip()
    return out[:limit] if out else ""


def _r1_respond(item: str, judge: str, opinion: str) -> dict:
    """R0 批阅（批准/驳回/修改）后，R1 自己判断是否需要重新派发任务给员工执行。

    返回 {"dispatch": bool, "task": str}；判不了返回 None（调用方回退规则）。"""
    prompt = (
        "你是老板助理 R1。R0 对批阅台待决 #%s 的裁决：%s。批注意见：%s。\n"
        "该待决条目的「决策建议」全文如下（R0 批阅意见往往只是简称，方案定义以此为准）：\n%s\n"
        "请判断是否需要**新派发任务给员工执行**：\n"
        "- 批准：通常需派发执行该决策（落地/上线等）；若只是记录性确认、无需新执行，则不派发。\n"
        "- 修改：通常需派发让执行角色按批注修改后重报。\n"
        "- 驳回：一般=否掉该项，无需再派发。\n"
        "生成 task 文本时必须把方案的具体边界写进去（不得只写「实现方案A」这类简称）。\n"
        "输出 JSON：{\"dispatch\": true|false, \"task\": \"<若要派发的任务文本，不派发则留空>\"}。只输出 JSON。"
        % (item, judge, opinion, decision_context("待决 #%s" % item) or "（条目未附决策建议）"))
    text = _headless_text(prompt, 300)
    if not text:
        return None
    d = _parse_kb_digest(text)
    if not isinstance(d, dict):
        return None
    return {"dispatch": bool(d.get("dispatch")), "task": str(d.get("task") or "")}


def piyue_report(task_no: str, task_text: str, ok_cnt: int, total: int, fail: list) -> int:
    """任务自动执行完成后：R1 整理回报呈报 R0。

    - 例行进展（默认）→ 追加「### 工作 N」到「## 工作内容」（查看即可，R0 可一键归档）；
    - 命中决策信号（定价/拍板/是否…/请 R0）→ 追加「### 待决 N」到「## 决策裁决」（需 R0 拍板）。
    段落格式与 parsers.parse_piyuetai / review.write_piyue 兼容。返回编号（失败返回 None）。"""
    try:
        rel = config.PIYUETAI_REL
        p = config.ROOT / rel
        text = config.read_text(p) if p.exists() else ""
        n = _piyue_next_no(text)          # 现有条目最大编号 +1（无则从 1 起）
        brief = "无回报正文"
        reps = []
        try:
            reps = store.reports(task_no)
        except Exception:
            reps = []
        try:
            if reps:
                # R 建议：逐角色给一段摘要（每人一行续行），不再是只取最后一份的 130 字压缩
                parts = []
                for rp in reps:
                    rb = str(rp.get("body") or "")
                    one = _one_line_digest(rb, limit=170) or "无正文内容"
                    parts.append("%s（%s）：%s" % (rp.get("role") or "?", rp.get("status") or "?", one))
                brief = "\n".join(parts)
        except Exception:
            pass
        task_s = (task_text or "").replace(chr(10), " ").replace("|", "／")
        # 条目 schema：标题只到任务号；长内容字段（回报摘要 / R 建议）保留原始 md 换行与标记，UI 按 markdown 渲染
        prog = "%d/%d 子任务完成%s，回报与产物已归档入库" % (ok_cnt, total, "" if not fail else "；阻塞 " + ",".join(fail))
        # R1 汇总：无论例行进展还是待决，都生成（R0 查看/决策都需要全量产出汇总）
        sum_rel = ""
        try:
            sum_rel = work_summary(task_no)      # R1 汇总全部 subagent 产出（代码类附变更与目录树）
        except Exception:
            sum_rel = ""
        # 分界线（结构化判定）：只有角色在回报「## 需要 R0 拍板」小节里声明的事项才进决策裁决，
        # 其余一律「工作内容」；角色已有建议、R1 能直接派发的按模板写在「## 后续动作」。
        pending = _pending_items(reps)
        need = bool(pending)
        advice = ""
        if need:
            try:
                advice = _advice_summary(reps, task_text)
            except Exception:
                advice = ""
        if need and not advice:
            # 判定要拍板但正文没写出来：摘要必须自报身份，不能冒充「决策建议」正文
            # （否则界面上看到的是各角色产出原文，读者以为就是模板化的建议）。
            advice = "（R1 按《模板-决策建议》提炼未完成，以下为角色声明原文，仅供 R0 参考）\n" + pending
        if need:
            lines_b = ["### 待决 %d｜任务 %s" % (n, task_no)]
            lines_b += _field_lines("任务", task_s[:160])
            lines_b += _field_lines("进展", prog)
            # 原「决策内容 / 决策建议」两栏合并为一栏：拍什么（决策点+现状背景）与怎么看（建议+动作）同源生成
            lines_b += _field_lines("决策建议", advice)
            lines_b += ["- **R0 批阅**：待填"]
            if sum_rel:
                lines_b += ["- **汇总文件**：" + sum_rel]   # 待决也挂 R1 汇总
            blk = chr(10) + chr(10).join(lines_b) + chr(10)
            section = "## 决策裁决"
        else:
            head = "### 工作 %d｜任务 %s" % (n, task_no)
            lines_b = [head]
            lines_b += _field_lines("任务", task_s[:160])
            lines_b += _field_lines("进展", prog)
            if sum_rel:
                lines_b += ["- **汇总文件**：" + sum_rel]
            blk = chr(10) + chr(10).join(lines_b) + chr(10)
            section = "## 工作内容"
        text = insert_block(text, section, blk)
        p.write_text(text, encoding="utf-8")
        return n
    except Exception:
        return None


def clean_task_files(no: str) -> int:
    """删除某任务在工作区/公共项目区的产出文件（子任务正文 / .meta.json / 汇总 / 回报，含已归档/）。

    按 no + "-" 前缀匹配（T-004-*），覆盖 T-004-S1.md、T-004-S1.meta.json、T-004-summary.md 等；
    不会误伤 T-0010（它不是以 T-001- 开头）。"""
    removed = 0
    # 公共项目区（项目/）下该任务的产物（T-xxx-*，含子目录）
    if config.PROJECT_ROOT.is_dir():
        import shutil as _sh
        for p in sorted(config.PROJECT_ROOT.rglob(no + "-*"), key=lambda x: -len(x.parts)):
            try:
                if p.is_dir():
                    _sh.rmtree(p, ignore_errors=True)
                else:
                    p.unlink()
                removed += 1
            except OSError:
                pass
    for d in _wb_role_dirs():
        for p in list(d.glob(no + "-*.md")) + list(d.glob(no + "-*.json")):
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
        arc = d / "已归档"
        if arc.is_dir():
            for p in list(arc.glob(no + "-*.md")) + list(arc.glob(no + "-*.json")):
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    pass
    return removed


def rn_outputs(no: str = "") -> list:
    """扫描《工作区/》各角色目录的产出（跳过 已归档/）；no 给出时只保留该任务编号的产出。"""
    out = []
    for d in _wb_role_dirs():
        files = []
        for p in sorted(d.glob("*.md")):
            text = config.read_text(p)
            if no and no not in text and no not in p.name:
                continue
            stem = p.stem
            for suf in ("-report", "-output"):
                if stem.endswith(suf):
                    stem = stem[: -len(suf)]
                    break
            meta_p = d / (stem + ".meta.json")
            st = ""
            if meta_p.exists():
                try:
                    st = str(json.loads(config.read_text(meta_p)).get("status") or "")
                except Exception:
                    st = "元数据损坏"
            files.append({"name": p.name, "rel": p.relative_to(config.ROOT).as_posix(),
                          "mtime": p.stat().st_mtime, "status": st, "head": text[:200]})
        if files:
            out.append({"dir": d.name, "files": files})
    return out


# ================= 04 项目文件：各角色工作区浏览器（按角色/任务筛选，可读文件才放行预览） =================
_WS_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".psd", ".ai",
                  ".zip", ".rar", ".7z", ".gz", ".tar", ".exe", ".dll", ".so", ".pyc",
                  ".db", ".sqlite", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                  ".mp3", ".mp4", ".wav", ".avi", ".mov", ".woff", ".woff2", ".ttf", ".otf",
                  ".class", ".o", ".obj", ".bin", ".dat", ".wasm", ".jar"}
_WS_SKIP_PARTS = {"node_modules", ".git", "__pycache__", ".dsh-tmp"}
_WS_MAX_BYTES = 3 * 1024 * 1024        # 在线预览上限 3 MB


def ws_files() -> list:
    """扫描《工作区/<角色>/》文件 → 产物清单（供按 角色/任务 筛选）。

    只收人读产物：md 交付物（-report / -output / -summary / 其它 .md）与普通文本；
    .meta.json 是机器状态文件不进产物列表。同角色同名文件同时存在于当前与 已归档/ 时只留当前副本。"""
    raw = []
    try:
        from . import roles as _roles
        _no_of = {config.sanitize_dir(n): no for no, n in _roles.role_files()}
    except Exception:
        _no_of = {}
    ws = config.WORKSPACE_ROOT
    if not ws.is_dir():
        return []
    for d in sorted(ws.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file() or any(seg in _WS_SKIP_PARTS for seg in p.relative_to(ws).parts):
                continue
            if p.suffix.lower() == ".json":            # meta.json = 元数据，不展示
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            m = re.search(r"T-\d+", p.name)
            rel = p.relative_to(config.ROOT).as_posix()
            raw.append({"role": d.name, "roleNo": _no_of.get(d.name, ""), "name": p.name, "rel": rel,
                        "ext": p.suffix.lower(), "task": m.group(0) if m else "",
                        "archived": "已归档" in p.relative_to(d).parts,
                        "size": st.st_size, "mtime": int(st.st_mtime)})
    seen = {}
    for f in raw:
        key = (f["role"], f["name"])
        cur = seen.get(key)
        if cur is None or (cur["archived"] and not f["archived"]):
            seen[key] = f
    return sorted(seen.values(), key=lambda f: (f["role"], f["name"], f["rel"]))


def home_stats() -> dict:
    """首页两块新面板的数据聚合：调度与用量（D）+ 项目进度（C）。

    一次请求拿全，避免首页开多个接口。全部从现有落盘数据推导，不引入新模型：
    调度状态与运行中执行取自 SCHED_STATE / _EXEC_STATE，用量取自各 meta.json，
    进度取自任务台账 + 项目/知识库/简报的文件统计。"""
    # —— 调度与用量 ——
    st = dict(SCHED_STATE)
    running = []
    try:
        role_of = {}
        for t in store.tasks():
            for s in store.subtasks(t["no"]):
                role_of[s["no"]] = s.get("role") or ""
        for act, s in (runner.exec_state() or {}).items():
            running.append({"sub": act, "role": role_of.get(act, ""),
                            "elapsed": int(s.get("elapsed") or 0),
                            "tools": int(s.get("tools") or 0)})
        running.sort(key=lambda x: x["sub"])
    except Exception:
        running = []
    rows = token_rows()
    by_day = {}
    for r in rows:
        b = by_day.setdefault(str(r.get("date") or "")[:10], {"in": 0, "out": 0})
        b["in"] += int(r.get("tokensIn") or 0)
        b["out"] += int(r.get("tokensOut") or 0)
    today = datetime.date.today().isoformat()
    week = []
    for i in range(6, -1, -1):
        d = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        b = by_day.get(d) or {"in": 0, "out": 0}
        week.append({"date": d[5:], "in": b["in"], "out": b["out"]})
    tin = by_day.get(today, {}).get("in", 0)
    tout = by_day.get(today, {}).get("out", 0)
    cost_today = tin / 1e6 * config.TOKEN_PRICE_IN + tout / 1e6 * config.TOKEN_PRICE_OUT
    tot_in = sum(b["in"] for b in by_day.values())
    tot_out = sum(b["out"] for b in by_day.values())
    # —— 项目进度 ——
    tasks = store.tasks()
    done = [t for t in tasks if "完成" in str(t.get("status") or "")]
    subs_total = subs_done = blocked = 0
    for t in tasks:
        for s in store.subtasks(t["no"]):
            subs_total += 1
            stt = str(s.get("st") or "")
            if "完成" in stt or "部分" in stt:
                subs_done += 1
            if "阻塞" in stt:
                blocked += 1
    proj = config.ROOT / "项目"
    proj_files = 0
    if proj.is_dir():
        proj_files = sum(1 for p in proj.rglob("*") if p.is_file()
                         and ".git" not in p.parts and "__pycache__" not in p.parts)
    kb = 0
    kbd = config.ROOT / "知识库"
    if kbd.is_dir():
        kb = sum(1 for p in kbd.rglob("*.md") if p.is_file())
    daily = len(list((config.ROOT / "批阅台").glob("每日简报-*.md")))
    recent = [{"no": t.get("no"), "title": str(t.get("task") or "")[:46]}
              for t in done[-3:]]
    return {
        "ok": True,
        "sched": {"busy": bool(st.get("busy")), "paused": bool(st.get("paused")),
                  "tag": str(st.get("tag") or ""), "running": running},
        "tokens": {"todayIn": tin, "todayOut": tout, "costToday": round(cost_today, 4),
                   "totalIn": tot_in, "totalOut": tot_out, "week": week,
                   "priceIn": config.TOKEN_PRICE_IN, "priceOut": config.TOKEN_PRICE_OUT},
        "progress": {"tasksTotal": len(tasks), "tasksDone": len(done),
                     "subsTotal": subs_total, "subsDone": subs_done, "blocked": blocked,
                     "projFiles": proj_files, "kbEntries": kb, "dailyReports": daily,
                     "recent": recent},
    }


def insert_block(text: str, section: str, blk: str) -> str:
    """把条目块插到 section 区段末尾（下一个「真正的」二级标题之前）。

    不能用 text.find("## ") 找区段末尾：字符串 "### 待决 8" 的后三位恰好是 "## "
    （## + 空格），会命中三级标题的第 1 个字符位置、把标题从中间劈开——原行被切成
    "#" 与 "## 待决 8"，条目降级成二级标题，解析器（三级标题 + 待决）再也认不出，界面上
    直接消失（T-007 待决插入时把 T-006 那条劈坏，就是这么丢的）。"""
    idx = text.find(section)
    if idx < 0:
        if not text.strip():
            return section + "\n" + blk
        return text.rstrip() + "\n\n" + section + "\n" + blk
    m2 = re.search(r"(?m)^## (?!#)", text[idx + len(section):])
    if not m2:
        return text.rstrip() + "\n" + blk
    cut = idx + len(section) + m2.start()
    return text[:cut] + blk + "\n" + text[cut:]


def token_rows() -> list:
    """从各角色工作区 meta.json（当前 + 已归档）读 token 统计行（meta 里 tokensIn/tokensOut）。"""
    rows = []
    ws = config.WORKSPACE_ROOT
    if not ws.is_dir():
        return rows
    for d in sorted(ws.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        for base in (d, d / "已归档"):
            if not base.is_dir():
                continue
            for meta_p in sorted(base.glob("*.meta.json")):
                try:
                    m = json.loads(meta_p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if m.get("tokensIn") is None and m.get("tokensOut") is None:
                    continue
                sub = str(m.get("subNo") or "")
                if not sub:
                    continue
                rows.append({"sub": sub, "task": str(m.get("taskNo") or ""),
                             "role": str(m.get("role") or ""), "roleName": str(m.get("roleName") or ""),
                             "date": str(m.get("createdAt") or "")[:10],
                             "tokensIn": int(m.get("tokensIn") or 0),
                             "tokensOut": int(m.get("tokensOut") or 0),
                             "archived": base.name == "已归档"})
    seen = {}
    for r in rows:
        key = (r["task"], r["sub"])
        cur = seen.get(key)
        if cur is None or (cur["archived"] and not r["archived"]):
            seen[key] = r
    return sorted(seen.values(), key=lambda r: (r["task"], r["sub"]))


def ws_read(rel: str) -> dict:
    """读取《工作区/》文件内容供预览：md 原样返回（前端渲染）；其余可解码文本以 txt 预览；
    二进制 / 不可读 / 过大一律不放行（只允许工作区根内，防路径逃逸）。"""
    root = config.ROOT.resolve()
    p = (root / rel).resolve()
    if not str(p).startswith(str(root)) or not p.is_file():
        raise ValueError("文件不存在或路径越界")
    try:
        size = p.stat().st_size
    except OSError:
        raise ValueError("文件不可读")
    if size > _WS_MAX_BYTES:
        raise ValueError("文件过大（超过 %d MB），不提供在线预览" % (_WS_MAX_BYTES // (1024 * 1024)))
    data = p.read_bytes()
    if p.suffix.lower() in _WS_BINARY_EXT or b"\x00" in data[:4096]:
        raise ValueError("二进制 / 不可读文件，已禁止查看")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("gbk")
        except UnicodeDecodeError:
            raise ValueError("无法按 UTF-8 / GBK 解码的文本文件，已禁止查看")
    return {"name": p.name, "kind": "md" if p.suffix.lower() == ".md" else "txt",
            "text": text, "rel": rel}


def task_output(no: str) -> dict:
    """按任务编号聚合输出：回报（DB）+ 子任务（DB）+ 工作区产物 + 调度日志片段。"""
    out = {"no": no,
           "reports": store.reports(no),
           "plan": store.subtasks(no),
           "executions": store.executions(no),
           "files": [], "log": ""}
    for d in _wb_role_dirs():
        for p in sorted((d / "已归档").glob("*.md")):      # 执行角色产物仅展示已归档文件
            if p.name.endswith("-summary.md"):
                continue
            text = config.read_text(p)
            if no in text or no in p.name:
                idx = max(text.find(no), 0)
                out["files"].append({"name": p.name,
                                     "rel": p.relative_to(config.ROOT).as_posix(),
                                     "head": text[:160],
                                     "seg": text[max(0, idx - 120):idx + 420]})
    lg = config.LOG_FILE
    if lg.exists():
        text = config.read_text(lg)
        idx = text.rfind(no)
        if idx >= 0:
            out["log"] = text[max(0, idx - 400):idx + 900]
    return out


def sub_output(sub_no: str) -> dict:
    """单个子任务的产出全文（工作区或已归档下的 {sub_no}.md），供工作台点击子任务查看。"""
    sub_no = (sub_no or "").strip()
    if not sub_no:
        return {}
    for d in _wb_role_dirs():
        for base in (d, d / "已归档"):
            p = base / (sub_no + "-report.md")
            if not p.exists():
                p = base / (sub_no + ".md")
            if not p.exists():
                continue
            meta = {}
            meta_p = base / (sub_no + ".meta.json")
            if meta_p.exists():
                try:
                    meta = json.loads(config.read_text(meta_p))
                except Exception:
                    meta = {}
            return {"rel": p.relative_to(config.ROOT).as_posix(),
                    "text": config.read_text(p),
                    "meta": meta}
    return {}


# ================= 05 OPC 时间轴：R1 模型提炼节点性/阶段性项目事件 =================
# 原 parsers.parse_timeline() 靠正则从决策日志 + 每日简报拼节点（含死板的「日报」节点与固定启动模板句）。
# 现改为：由 R1（dsh headless 模型）从各角色工作区产物 + 决策日志 D-NN + 任务台账里提炼
# 真正的「节点性 / 阶段性」项目里程碑，并让模型自写「说明文字」；日报不再进时间轴。
# 手动触发 + 缓存到《批阅台/时间轴.json》，模型不可用时返回空态提示。


def _timeline_input() -> str:
    """给 R1 模型汇总时间轴的输入：各角色工作区产物 + 决策日志 D-NN + 任务台账节点。"""
    from . import knowledge
    parts = []
    for grp in rn_outputs():
        lines = []
        for f in grp["files"]:
            st = f.get("status") or ""
            head = (f.get("head") or "").strip().replace("\n", " ")
            lines.append("- %s（%s）%s" % (f["name"], st, head[:120]))
        if lines:
            parts.append("## 角色工作区 · %s\n%s" % (grp["dir"], "\n".join(lines)))
    try:
        dtext = knowledge.read_md(config.LOG_REL)
        d = [m.group(1).strip() for m in re.finditer(r"^##\s+D-\d+｜(.+?)（\d{4}-\d{2}-\d{2}", dtext, re.M)]
        if d:
            parts.append("## 决策日志（里程碑条目）\n" + "\n".join("- " + x for x in d))
    except Exception:
        pass
    trows = []
    for t in store.tasks():
        subs = store.subtasks(t["no"])
        done = sum(1 for s in subs if (s.get("st") or "") == "完成")
        trows.append("- %s %s：%d/%d 子任务完成（%s）" % (t["no"], t.get("status") or "",
                                                        done, len(subs), (t.get("task") or "")[:60].replace("\n", " ")))
    if trows:
        parts.append("## 任务台账（节点性任务）\n" + "\n".join(trows[-20:]))
    return "\n\n".join(p for p in parts if p.strip())


def _parse_timeline_json(text: str):
    """从模型输出提取事件 JSON 数组（容忍模型用 json 代码块包裹 / 前后杂字）。"""
    t = re.sub(_TRIPLE_BT + r"(?:json)?", "", (text or ""), flags=re.I).strip()
    i, j = t.find("["), t.rfind("]")
    if i < 0 or j <= i:
        return None
    try:
        data = json.loads(t[i:j + 1])
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    out = []
    for it in data:
        if not isinstance(it, dict):
            continue
        date = str(it.get("date") or "").strip()[:10]
        title = str(it.get("title") or "").strip()[:40]
        detail = str(it.get("detail") or "").strip()[:400]
        if date or title:
            out.append({"date": date, "title": title, "detail": detail})
    out.sort(key=lambda e: e["date"])
    return out


def _write_timeline(events) -> str:
    p = config.ROOT / config.TIMELINE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"events": events,
                             "generated_at": datetime.datetime.now().isoformat(timespec="seconds")},
                            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p.relative_to(config.ROOT).as_posix()


def get_timeline() -> dict:
    """读时间轴缓存（模型上次生成的结果）；无缓存返回空态 + 提示，不自动生成。"""
    p = config.ROOT / config.TIMELINE_REL
    if not p.exists():
        return {"generated_at": None, "events": [],
                "msg": "尚未生成时间轴 — 点「生成时间轴」由 R1 从各角色工作区提炼"}
    try:
        obj = json.loads(config.read_text(p))
    except Exception:
        return {"generated_at": None, "events": [], "msg": "时间轴缓存不可读，请重新生成"}
    evs = obj.get("events") if isinstance(obj, dict) else []
    return {"generated_at": (obj.get("generated_at") if isinstance(obj, dict) else None),
            "events": evs if isinstance(evs, list) else []}


def build_timeline() -> dict:
    """让 R1 模型提炼「节点性 / 阶段性」项目事件，写缓存 JSON，返回结果。

    - 「说明文字」由模型总结；只列节点性里程碑，不列每日简报 / 流水账 / 例行任务。
    - 模型不可用 / 未配置 → 返回 {ok:False, msg}，前端显示空态提示（不再硬编旧节点）。"""
    data = _timeline_input()
    if not data.strip():
        return {"ok": False, "msg": "暂无可提炼的项目数据（角色工作区 / 决策日志 / 任务台账均为空）"}
    prompt = ("你是老板助理 R1，能看见所有角色工作区与项目状态。请把项目数据提炼成 OPC 时间轴——"
              "**按阶段归并**，不是把做过的事逐条列举。\n"
              "归并规则（重要）：\n"
              "- 同一主线、时间相邻的事合成一条：「设计稿交付」与「设计定稿（驳回后补写）」是一条；"
              "「工程化重构」「冗余清理」「目录成型」也同属一条。\n"
              "- 判据是「有没有改变项目所处阶段」：改变阶段才立条；同阶段内的执行、修改、补充都并进该阶段。\n"
              "- **按大阶段归并**：一个阶段要能独立成章、一句话说清这段时间在干什么。阶段数量由项目实际进展决定，不预设条数；同一大阶段内的所有任务、设计与实现都并进该阶段——宁可少而准，不要多而碎。\n"
              "输出 JSON 数组，每项：\n"
              "- date：该阶段起始日期 YYYY-MM-DD\n"
              "- title：阶段名，≤16 字，说清「完成了什么阶段」（如「设计定稿与开发启动」）\n"
              "- detail：两三句，讲这个阶段解决了什么、留下什么标志性产出（可含多个交付物）\n"
              "按 date 升序；没有符合的就输出 []。不要把每日简报、流水账、例行任务当成事件。"
              "只输出 JSON，不要任何多余文字。\n\n项目数据：\n%s" % data)
    text = _headless_text(prompt, 300)
    if not text:
        return {"ok": False, "msg": "模型未返回结果（请确认 dsh 与模型 API 可用）"}
    events = _parse_timeline_json(text)
    if events is None:
        return {"ok": False, "msg": "模型返回内容无法解析为事件列表，请重试"}
    rel = _write_timeline(events)
    return {"ok": True, "events": events, "msg": "已生成（" + rel + "）"}


def project_files() -> dict:
    """公共项目区（项目/）文件清单：源码/工程性产出。全员可读；仅「工程」标签角色可写。

    writers = 当前具备《项目/》写权限的角色（工程标签），供前端展示。"""
    from . import roles as _roles
    out = []
    root = config.PROJECT_ROOT
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if not p.is_file() or any(seg in _WS_SKIP_PARTS for seg in p.relative_to(root).parts):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            out.append({"name": p.name, "rel": p.relative_to(config.ROOT).as_posix(),
                        "ext": p.suffix.lower(), "size": st.st_size, "mtime": int(st.st_mtime)})
    writers = [no for no, _ in _roles.role_files() if _roles.can_write_project(no)]
    return {"files": out, "writers": writers}

