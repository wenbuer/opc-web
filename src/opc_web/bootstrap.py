# -*- coding: utf-8 -*-
"""部署自举 v1.10：单根目录模型 —— 自动产生 批阅台/、工作区/、知识库/ 三个文件夹，
工作区按「角色名称」建子文件夹（旧结构一次性迁移后不再保留 决策/运营/营销 等静态分类）。
幂等：已存在的目录/种子文件不重建，可重复运行。"""
import shutil

from . import config

BOOT_LOG = []


def init_agents():
    """项目自己的 agents/：为空时按当前项目模板生成角色卡。

    角色阵容跟项目走 —— 一个项目要「大型开发」，另一个要「小微 App」，两边互不干扰。
    没激活项目时 AGENTS_DIR 指向模板库本身，不生成；已有 agents/ 不覆盖。"""
    if not config.active_project():
        return
    d = config.AGENTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    if any(d.glob("R*.role.md")):
        return
    from . import roles as _roles, templates as _tpl
    tpl = config.current_template()
    n = 0
    for r in tpl["roles"]:
        card = _roles.role_card(r["no"], r["name"], r["duties"], r["position"], r["type_"], (), tags=r.get("tags") or ())
        (d / (r["no"] + ".role.md")).write_text(card, encoding="utf-8")
        n += 1
    if n:
        BOOT_LOG.append("角色卡初始化：按模板「%s」生成 %d 张 → %s" % (tpl["name"], n, d))


def bootstrap():
    BOOT_LOG.clear()          # 只报本次，不累积历史
    init_agents()
    for d in (config.BATCH_ROOT, config.WORKSPACE_ROOT, config.KB_ROOT, config.PROJECT_ROOT):
        d.mkdir(parents=True, exist_ok=True)
    # 角色工作区：按「角色名称」建目录（v1.10）；角色技能共享库 agents/skills/（平铺，卡上登记即装配）
    try:
        from . import roles as _roles
        active = bool(config.active_project())
        for _no, _name in _roles.role_files():
            (config.WORKSPACE_ROOT / config.sanitize_dir(_name)).mkdir(parents=True, exist_ok=True)
        if active:
            (config.AGENTS_DIR / config.SKILLS_REL).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    h = chr(10)
    # 知识库分类目录（含「OPC 规范」——员工手册归宿）：建目录便于沉淀与手册落盘
    for cat in config.KB_CATEGORIES:
        (config.KB_ROOT / cat).mkdir(parents=True, exist_ok=True)
    from . import templates as _tpl
    # 员工手册默认入知识库：优先用随包分发的 _seed/员工手册.md（打包场景，内容可随包替换），
    # 否则回退内置权威文本 handbook_text()。
    _seed_hb = config.BASE / "_seed" / "员工手册.md"
    hb = (_seed_hb.read_text(encoding="utf-8") if _seed_hb.is_file() else _tpl.handbook_text())
    seeds = {
        config.LOG_REL: "## 决策日志" + h,
        # 批阅台：空骨架 = 工作内容（例行进展）/ 决策裁决（需 R0 拍板）/ 已批阅归档 三区
        config.PIYUETAI_REL: "## 工作内容" + h + h + "## 决策裁决" + h + h + "## 已批阅归档" + h,
        # 员工手册：全员唯一行为准则（OPC智能体角色架构.md / 知识库索引.md 已移除：不作为知识档案入库）
        config.HANDBOOK_REL: hb,
    }
    for rel, text in seeds.items():
        p = config.ROOT / rel
        if not p.exists():
            p.write_text(text, encoding="utf-8")
            BOOT_LOG.append("创建 " + rel)
    if not config.LOG_FILE.exists():
        config.LOG_FILE.write_text("## R1 调度日志" + h, encoding="utf-8")
        BOOT_LOG.append("创建 " + config.SCHED_LOG_REL)


if __name__ == "__main__":
    bootstrap()
    for ln in BOOT_LOG:
        print(ln)
