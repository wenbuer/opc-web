# -*- coding: utf-8 -*-
"""可装配技能的来源扫描（与执行引擎无关）。

技能是**项目资产**，不是某个引擎的能力：技能 md 由控制台导入到共享技能库
`agents/skills/`，装配关系登记在角色卡「## 技能」段，执行时由 `agent.agent_prompt()`
把技能正文拼进 prompt —— 谁在执行（dsh / 直连 API）都吃同一份，技能本身是跨引擎的。

所以「有哪些技能可导入」扫的是**本机技能源**，跟当前引擎无关；
引擎只在 `capabilities()["skills"]` 上声明一件事：能不能直接执行技能里那些
需要工具 / 脚本 / 沙箱的步骤（dsh 能，内置 4 个工具的直连 API 引擎跑不动）。
"""
import os
import re
from pathlib import Path


def sources() -> list:
    """候选技能目录（同名去重，先到先得）：dsh 用户级 → agents 平台 → npm 插件包。"""
    home = Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))
    dirs, seen = [], set()

    def add(p):
        if p.is_dir() and (p / "SKILL.md").exists() and p.name not in seen:
            seen.add(p.name)
            dirs.append(p)

    def add_root(root):
        if root.is_dir():
            for p in sorted(root.iterdir()):
                add(p)

    add_root(home / "skills")                        # ~/.dsh/skills
    add_root(Path.home() / ".agents" / "skills")     # ~/.agents/skills
    prof = home / "profiles"
    if prof.is_dir():
        for pd in sorted(prof.iterdir()):
            nm = pd / "node_modules"
            if nm.is_dir():
                for sk in sorted(nm.glob("**/skills/*/SKILL.md")):
                    add(sk.parent)
    return sorted(dirs, key=lambda p: p.name.lower())


def describe(skill_md) -> str:
    """从 SKILL.md 的 front-matter 里摘 description（供技能页显示一行说明）。"""
    try:
        txt = Path(skill_md).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    m = re.search(r"^---\s*\n([\s\S]*?)\n---", txt)
    fm = m.group(1) if m else ""
    dm = re.search(r"(?m)^description:\s*[>|]?\s*([\s\S]*?)(?=^---|\Z)", fm)
    return " ".join((dm.group(1) or "").split())[:200] if dm else ""
