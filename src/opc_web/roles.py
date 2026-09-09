# -*- coding: utf-8 -*-
"""角色管理（v1.9+）：角色卡由本项目自己维护（agents/，不写入全局 dsh 配置）；
新增角色 agent：自动编号 / 角色卡 / 工作区（角色卡为唯一权威，无架构登记）。

v1.9 语义：web 引用与工作区创建一律使用「角色名称」，R1/R2 仅为编号 Id——
工作区目录 = 《工作区/<角色名称>/》（v1.10 三目录模型，无 -输出 后缀）。

角色「技能装配」：技能 md 平铺共享在 agents/skills/<技能名>.md，角色卡「## 技能」段
登记装配清单（每行一个技能文件名）；agent_prompt() 按清单把技能正文注入派发 prompt。
"""
import datetime
import re

from . import config

# 角色卡只描述「你是谁、干什么」；行为纪律（不拍板/读写权限/产出回报格式/状态字段）一律以《员工手册》为准。
CARD_TPL = """# OPC 角色卡：%(no)s %(name)s

## 身份
- 编号：%(no)s｜名称：%(name)s｜类型：%(type_)s
- 一句话定位：%(position)s
- 标签：%(tags)s
- 上级：%(superior)s

## 职责
%(duties)s

## 技能
%(skills)s

## 行为准则
- 唯一遵守《员工手册》（知识库/OPC 规范/员工手册.md）：不拍板、不花钱、不发布
- 读写权限、产出与回报格式、技能装配、状态字段 一律按《员工手册》执行
"""


def role_files():
    """列出已有角色 [(no, 名称)]（名称取自角色卡「身份·名称」，web 引用用名称）。"""
    out = []
    for p in sorted(config.AGENTS_DIR.glob("R*.role.md")):
        m = re.match(r"R(\d+)\.role\.md", p.name)
        if not m:
            continue
        no = "R" + m.group(1)
        name = config.role_name(no)
        out.append((no, name))
    out.sort(key=lambda x: int(x[0][1:]))
    return out


def next_no():
    return "R%d" % (max([int(no[1:]) for no, _ in role_files()] or [0]) + 1)


def role_duty(no: str) -> str:
    """角色卡「## 职责」段首条 → 一句话职责（拆解器/速览表用）。"""
    p = config.AGENTS_DIR / (no + ".role.md")
    if not p.exists():
        return ""
    m = re.search(r"##\s*职责[^\n]*\n+\s*-\s*([^\n]+)", config.read_text(p))
    return m.group(1).strip() if m else ""


_TAGS_RE = re.compile(r"-\s*标签\s*[:：][ \t]*([^\n]+)")


def _tags_from_text(text):
    """从角色卡文本提取标签列表（空格/英文、中文逗号分隔）；无标签行返回 []。"""
    m = _TAGS_RE.search(text or "")
    if not m:
        return []
    return [t for t in re.split(r"[\s,，、;；]+", m.group(1).strip()) if t and t != "未定级"]


def role_tags(no: str) -> list:
    """读取角色卡「## 身份」段的「标签：」行 → 标签列表（业务/工程/枢纽…）。"""
    p = config.AGENTS_DIR / (no + ".role.md")
    if not p.exists():
        return []
    return _tags_from_text(config.read_text(p))


def can_write_project(no: str) -> bool:
    """工程标签角色可写公共项目区（项目/），其他角色只读。"""
    return "工程" in role_tags(no)


def role_digest(exclude=("R0", "R1")):
    """角色摘要 [(编号, 名称, 一句话职责)] —— 给任务拆解器认人用。

    只给编号+名称时模型只能靠名字猜（「本周产品动态提纲」该给 R3 内容工厂还是
    R4 增长与数据？），带上首条职责就能判准。整卡 5000+ 字塞进 prompt 只会稀释
    注意力，取「## 职责」段首条即可。默认剔除 R0/R1：派发者不能是被派发对象。"""
    out = []
    for no, name in role_files():
        if no in exclude:
            continue
        out.append((no, name, role_duty(no)))
    return out


def role_card(no, name, duty, position, type_="业务", skills=(), tags=()):
    """组装新角色卡（CARD_TPL + 运行时变量）；skills = 装配技能名列表；tags = 角色标签（业务/工程…）。

    duty 可为字符串（每行一条）或列表（模板 _role 传的是列表）。"""
    today = datetime.date.today().isoformat()
    if isinstance(duty, (list, tuple)):
        lines = [str(d) for d in duty]
    else:
        lines = [s.strip() for s in str(duty).replace(chr(13), "").split("\n") if s.strip()]
    duties = "\n".join("- " + s.strip() for s in lines if s.strip())
    rows = ["- " + str(s).strip() for s in skills if str(s).strip()]
    if not rows:
        rows = ["- （未装配：在 agents/skills/ 放技能 md 后，在这里登记文件名，每行一个）"]
    kb = str(config.ROOT).replace("\\", "/")
    ws = config.WORKSPACE_REL
    return CARD_TPL % {
        "no": no, "name": name, "today": today,
        "type_": type_, "position": position,
        "duties": duties, "skills": "\n".join(rows),
        "tags": " ".join(tags),
        "kb": kb, "ws": ws, "wsname": name,
        # R1 自己的上级是 R0 老板（下达任务、批阅裁决）；其余角色上级是 R1 枢纽（接受派发、回报确认）
        "superior": "R0 老板（下达任务、批阅裁决）" if no == "R1" else "R1 老板助理（接受派发、回报确认）",
    }


def add_role(name, duty, position, type_="业务", skills=(), tags=(), dry=False):
    """新增角色 agent：编号 → 角色卡 → 工作区目录《<角色名称>》。
    dry 只返回预览。角色卡只写本项目 agents/（唯一权威），不写入全局 dsh 配置，也不同步架构表。"""
    if not config.active_project():
        raise ValueError("还没有激活的项目：请先在「设置 → 项目」新建或选择一个项目，再新增角色")
    no = next_no()
    card = role_card(no, name, duty, position, type_, skills or (), tags=tags)
    wsname = config.sanitize_dir(name)
    result = {
        "no": no, "name": name, "card": card,
        "cardPath": str(config.AGENTS_DIR / (no + ".role.md")),
        "wsRel": "%s/%s" % (config.WORKSPACE_REL, wsname),
        "sbRoot": (config.WORKSPACE_ROOT / wsname).as_posix(),
        "tags": list(tags),
    }
    if dry:
        return result
    (config.AGENTS_DIR / (no + ".role.md")).write_text(card, encoding="utf-8")
    (config.WORKSPACE_ROOT / wsname).mkdir(parents=True, exist_ok=True)
    return result


def remove_role(no: str) -> dict:
    """删除角色 agent：角色卡 + 工作区《名称/》。功能权威=角色卡，无需同步架构表。
    守卫：① 有进行中/待派子任务 → 拒删（防幽灵派发）；② 工作区有未归档产物 → 拒删（防数据丢失）。
    安全：R0（创始人）/R1（枢纽）不可删除，其余 R2+ 可删。返回 {no, name, removed, roleLeft}。"""
    no = (no or "").strip().upper()
    if no in ("R0", "R1"):
        raise ValueError("角色 %s（创始人/枢纽）受保护，不可删除" % no)
    p = config.AGENTS_DIR / (no + ".role.md")
    if not p.exists():
        raise ValueError("角色卡 %s 不存在" % no)
    name = config.role_name(no)
    wsname = config.sanitize_dir(name if name != no else no)
    ws = config.WORKSPACE_ROOT / wsname
    # 守卫①：该角色有进行中/待派/已派子任务 → 拒删（删除后这些任务会派发到幽灵角色）
    try:
        from . import store as _store
        pending = [s for s in _store.subtasks()
                   if s["role"] == no and s["st"] in ("待派", "已派", "执行中")]
    except Exception:
        pending = []
    if pending:
        tasknos = "、".join(sorted({s["taskNo"] for s in pending}))
        raise ValueError("角色 %s 有 %d 个进行中/待派子任务（%s），不可删除：请先在《工作台》处理这些任务（完成/驳回/删除）"
                         % (no, len(pending), tasknos))
    # 守卫②：工作区有未归档产物 → 拒删（防止未入库数据被 rmtree 丢弃）
    if ws.exists():
        leftovers = [f for f in ws.rglob("*") if f.is_file() and "已归档" not in f.parts]
        if leftovers:
            raise ValueError("角色 %s 工作区《工作区/%s/》尚 %d 个未归档文件（如 %s…），不可删除：请先在《工作台》整理归档，或手动移走后再删"
                             % (no, wsname, len(leftovers), leftovers[0].name))
    removed = []
    # 1) 角色卡（本项目 agents/）
    p.unlink()
    removed.append(str(p))
    # 3) 工作区《工作区/<名称>/》（v1.10 名称工作区；旧 R?-输出 目录不在本次删除范围内）
    if ws.exists():
        import shutil
        shutil.rmtree(ws, ignore_errors=True)
        removed.append(str(ws))
    return {"no": no, "name": name, "removed": removed, "roleLeft": len(role_files())}


def _card_sections(text):
    """把角色卡按 ## 段切成 {段名: [行,...]}。"""
    seg = {}
    cur = None
    for ln in text.split("\n"):
        if ln.startswith("## "):
            cur = ln[3:].strip()
            seg[cur] = []
            continue
        if cur:
            seg[cur].append(ln)
    return seg


def _skill_items(lines):
    """技能段行 → 装配技能名（跳过空行与以 （ / ( 开头的提示行）。"""
    out = []
    for ln in lines:
        t = ln.strip()
        if t.startswith("- "):
            s = t[2:].strip()
            if s and not (s.startswith("（") or s.startswith("(")):
                out.append(s)
    return out


def card_skills(text: str) -> list:
    """角色卡文本「## 技能」段 → 装配技能名列表（文件名，可带 .md 后缀）。"""
    return _skill_items(_card_sections(text).get("技能", []))


def role_skill_names(no: str) -> list:
    """读取角色卡文件，返回该角色登记的装配技能名列表。"""
    p = config.AGENTS_DIR / (no + ".role.md")
    if not p.exists():
        return []
    return card_skills(config.read_text(p))


def _extract_fields(text):
    """从现角色卡提取 (no, name, type_, position, duties, skills)。"""
    seg = _card_sections(text)
    ident = [ln for ln in seg.get("身份", [])]
    no = name = type_ = ""
    for ln in ident:
        s = ln.strip()
        if s.startswith("- 编号："):
            for part in s[4:].split("｜"):
                k, _, v = part.partition("：")
                if k == "编号": no = v
                elif k == "名称": name = v
                elif k == "类型": type_ = v
        if s.startswith("- 一句话定位："):
            position = s.split("：", 1)[1].strip()
    if "position" not in locals():
        position = "一句话定位"
    duties = "\n".join(ln.strip()[2:].strip() for ln in seg.get("职责", []) if ln.strip().startswith("- "))
    skills = _skill_items(seg.get("技能", []))
    return no or "R?", name, type_, position, duties, skills


def edit_role(no, name=None, duty=None, position=None, type_=None, skills=None, tags=None, card=None, dry=False):
    """编辑角色卡。缺省字段取自现卡；重生成并覆写角色卡。dry 只返回预览。
    skills=None → 保留现卡装配清单（UI 没动技能时不会清空）；传 [] 才清空。
    card 非空 → 整卡 Markdown 直接覆写（保留 行为准则 等全部段落），
    不再走 role_card 模板重建（模板只覆盖 no/name/type/position/职责/技能，保存会丢其他段落）。"""
    p = config.AGENTS_DIR / (no + ".role.md")
    if not p.exists():
        raise ValueError("角色 %s 不存在" % no)
    if card is not None and str(card).strip():
        card = str(card).replace("\r\n", "\n").replace("\r", "\n")
        if not re.search(r"^#\s*OPC", card, re.M):
            raise ValueError("角色卡必须以 # OPC 开头")
        result = {"no": no, "name": name, "card": card, "cardPath": str(p)}
        if dry:
            return result
        p.write_text(card, encoding="utf-8")
        return result
    text = config.read_text(p)
    c_no, c_name, c_type, c_pos, c_duties, c_skills = _extract_fields(text)
    name = name or c_name or "未命名"
    type_ = type_ or c_type or "业务"
    position = position or c_pos or "一句话定位"
    duty = duty or c_duties or "待补充职责"
    if skills is None:
        skills = c_skills
    if tags is None:
        tags = _tags_from_text(text)
    rebuilt = role_card(no, name, duty, position, type_, skills, tags=tags)
    result = {"no": no, "name": name, "card": rebuilt, "cardPath": str(p)}
    if dry:
        return result
    p.write_text(rebuilt, encoding="utf-8")
    return result