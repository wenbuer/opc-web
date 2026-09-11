# -*- coding: utf-8 -*-
"""角色派发（delegate）通道：角色卡装配 + subagent 派发规格。

角色定义由本项目自己维护（agents/R?.role.md）；web 引用与工作区一律用「角色名称」，
R1/R2 仅为编号 Id。执行方 = 常驻会话主 agent（R1 助理），向下派活 = DSH subagent。

v1.19 移除 DSH preset 通道：原设计想让「会话选择 preset → 派出的子 agent 自动继承
角色 persona」，但方向反了 —— subagent 继承的是父会话（R1 枢纽）的 preset，不是目标
角色的；且 subagent 工具本身没有指定 preset 的参数。角色 persona 实际一直只靠
agent_prompt() 把角色卡全文注入 prompt 生效，preset 资产从未参与自动派发。

角色「技能装配」（C 路线）：技能 md 平铺共享在 agents/skills/<技能名>.md，装配关系
登记在角色卡「## 技能」段；agent_prompt() 只注入**技能清单与路径**，正文由模型按需
读——不依赖 DSH 会话技能体系，headless / subagent 两条执行通道都生效。

v1.20 起不再把技能正文拼进 prompt：全文注入会让 R3 的执行 prompt 有九成是技能文本
（实测 16396/17383 字），而一次任务通常只真正用到一个技能。改成给清单 + 路径，
模型自己读那一篇。
"""
import datetime

from . import config, knowledge, roles, skills

SKILLS_REL = config.SKILLS_REL   # 角色技能共享库目录名（agents/skills/，见 config）


def role_skills(no: str) -> list:
    """按角色卡「## 技能」段登记的清单，列出技能库里的对应技能：{name, rel, desc}。

    技能 md 平铺共享、多角色可复用；装配关系登记在角色卡上（设置页编辑角色时
    若未改技能字段，会原样保留，不会因整卡重生成而丢装配）。

    只列清单、**不返回正文**（正文按需读，见 skills_block）。"""
    out = []
    for name in roles.role_skill_names(no):
        f = config.AGENTS_DIR / SKILLS_REL / (name if name.lower().endswith(".md") else name + ".md")
        if not f.is_file():
            continue
        try:
            rel = f.relative_to(config.ROOT).as_posix()
        except ValueError:
            rel = f.as_posix()
        out.append({"name": f.stem, "rel": rel, "desc": _skill_desc(f)})
    return out


def _skill_desc(f) -> str:
    """技能的一行说明：优先 front-matter 的 description，没有就取正文首句（截断）。"""
    try:
        d = skills.describe(f)
    except Exception:
        d = ""
    if not d:
        try:
            for ln in config.read_text(f).splitlines():
                ln = ln.strip()
                if ln and not ln.startswith(("#", "---", "|")):
                    d = ln
                    break
        except Exception:
            d = ""
    return " ".join(str(d or "").split())[:110]


def skills_block(no: str) -> str:
    """【装配技能】段落：技能清单 + 逐条路径 + 「先读再动手」的硬性要求。

    正文不进 prompt，所以这里必须把要求写死 —— 否则模型可能跳过读技能这一步，
    直接凭印象干活，技能就等于没装。"""
    items = role_skills(no)
    if not items:
        return ""
    lines = []
    for it in items:
        lines.append("· %s%s" % (it["name"], (" —— " + it["desc"]) if it["desc"] else ""))
        lines.append("  正文：%s" % it["rel"])
    return ("\n\n【装配技能】你装配了以下技能（共享技能库 agents/skills/，随项目分发）：\n"
            + "\n".join(lines)
            + "\n动手前先判断本任务用得上哪个技能，再用工具把那个技能 md **完整读一遍**，"
              "然后按它的规范执行；没读技能直接产出的结果视为不合格。"
              "技能要求与任务要求或 R0 意见冲突时，以后者为准。")


def agent_prompt(no: str, task_text: str, out_rel: str = "", meta_rel: str = "") -> str:
    """角色卡全文 + 装配技能 + 任务 + 工作根 + 产出约定 —— 子 agent 的 persona 就来自这里。

    v1.15：不再要求模型复述「回报人｜任务｜状态」尾行——任务号/角色中枢本来就知道，
    让模型复述已知信息只会带来漏写。模型只写正文，外加回填 meta.json 的 status 一个字段。"""
    card = config.AGENTS_DIR / (no + ".role.md")
    head = card.read_text(encoding="utf-8") if card.exists() else "OPC 角色 %s" % no
    kb = str(config.ROOT).replace("\\", "/")
    skills = skills_block(no)
    tail = ""
    if out_rel:
        tail = ("\n产出文件：%s —— 边做边追加进度，可写多次（有输出即视为存活）。"
                "\n回报请在最终写入时用固定小节（便于 R0 决策）："
                "\n## 结论 —— 一两句话说清结果；"
                "\n## 依据与要点 —— 关键信息 / 依据 / 过程；"
                "\n## 需要 R0 拍板 —— 仅在确有需要 R0 拍板的事项时写这一节，且必须把每个决策点写完整：现状背景 → 可选方案 → 你的建议（不要只写一句“请 R0 拍板”，也不要写“任务含决策信号 / 请 R0 裁决 / 驳回将重新派发”这类流程空话——R0 要读到的是一句话能看懂的具体决策点）；没有需要拍板的事项就整节不写。"
                "\n完成后：把 %s 里的 status 改为 完成 / 部分 / 阻塞（只改这一个字段，其余勿动）。"
                % (out_rel, meta_rel))
    # 知识库：全员只读，执行前建议先查相关档案与员工手册
    kb_note = ("\n\n【知识库】《知识库/》对全员只读开放：动手前先读与本任务相关的档案与《员工手册》，"
               "作为依据与规范。")
    idx = "\n".join(knowledge.index_lines())
    if idx:
        # 清单直接给出：省掉「先列目录发现有什么」那一轮工具调用（列一次的响应比整份索引还大）
        kb_note += "档案清单与路径如下（相对项目根），要正文就用工具直接读该路径，不必先列目录：\n" + idx
    # 公共项目区（项目/）：工程标签可写，其他只读 —— 落点控制 + 提示约定
    pj = ("\n\n【公共项目区】《项目/》是公共源码/工程性产出区：仅「工程」标签角色可写，其他角色只读。")
    if roles.can_write_project(no):
        pj += ("你是「工程」角色：技术产出/源码直接写到《项目/》下（不按任务建子文件夹，全部平铺于此），完成后在回报里说明落点。")
    else:
        pj += ("你不是「工程」角色：请勿写入《项目/》；若产出需落到项目区，交给工程角色或在回报中说明。")
    return (head + skills + "\n\n【任务】" + task_text +
            "\n工作根目录：" + kb + "（用 / 分隔路径，知识库唯一权威根）" + kb_note + tail + pj)


def subtask_spec(no: str, task_text: str, expect: str = "", sub_no: str = "") -> dict:
    """subagent 派发规格：角色 / 注入 prompt / 产出路径。
    主会话 R1 收到后据此调一次 DSH subagent（prompt=spec['prompt']）。

    产出按子任务编号命名（T-001-S1.md），不再是全角色共用的「回报-待落库.md」——
    共用固定名会让同角色的多个任务互相覆盖，且归档正则只认得第一条。"""
    if not sub_no:
        raise ValueError("subtask_spec 需要子任务编号：产出按编号命名，共用固定名会让同角色的多任务互相覆盖")
    d = "%s/%s" % (config.WORKSPACE_REL, config.role_dir(no))
    out_rel = "%s/%s-report.md" % (d, sub_no)      # 完成回报（人读交付物）
    meta_rel = "%s/%s.meta.json" % (d, sub_no)
    return {
        "role": no,
        "roleName": config.role_name(no),
        "prompt": agent_prompt(no, task_text, out_rel, meta_rel),
        "output": out_rel,
        "meta": meta_rel,
        "expect": expect,
    }


def log_schedule(tag: str, text: str):
    """统一调度日志（追加到《批阅台/调度日志.md》）。"""
    with open(str(config.LOG_FILE), "a", encoding="utf-8") as f:
        f.write("\n\n## 【调度指令】%s %s\n\n%s\n" % (tag, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), text))