# -*- coding: utf-8 -*-
"""调度自检：headless one-shot 已移除；角色卡经 prompt 注入装配正确（preset 通道已于 v1.19 删除）。
技能装配：共享库 agents/skills/ + 角色卡「## 技能」段登记。"""
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import agent, config  # noqa: E402


# 测试使用固定 7 角色阵容，避免受当前激活项目（模板可变）影响 —— 项目无关
STD_ROSTER = [
        ("R1","老板助理（枢纽）","枢纽","接收任务→拆解派发→汇总回报→呈报决策",["任务派发、调度与回报校验"],("枢纽",)),
        ("R2","需求研究员","业务","持续挖掘用户原声、维护需求假设清单",["用户原声挖掘、需求与假设清单维护"],("业务",)),
        ("R3","内容工厂","业务","生产内容稿、选题与话术语料",["生产内容稿、选题与话术语料"],("业务",)),
        ("R4","增长与数据","业务","增长实验落地 + 数据验证复盘",["增长实验落地与数据验证复盘"],("业务",)),
        ("R5","用户洞察官","业务","用户洞察与真实需求研究",["用户洞察与真实需求研究"],("业务",)),
        ("R6","产品设计师","业务","需求→功能/场景设计 + 前端实现编码",["产品设计 + 前端实现编码"],("业务",)),
        ("R7","技术评估与实现","技术","技术路径评估 + 实现编码",["技术路径评估与实现编码"],("工程",)),
]
_STD_AGENTS_TMP = Path(__file__).resolve().parent.parent / ".roster-agents"


def setUpModule():
    global _OLD_AGENTS
    _OLD_AGENTS = config.AGENTS_DIR
    import shutil as _sh
    _sh.rmtree(_STD_AGENTS_TMP, ignore_errors=True)
    _STD_AGENTS_TMP.mkdir(parents=True, exist_ok=True)
    from opc_web import roles as _r
    for no, name, type_, pos, duties, tags in STD_ROSTER:
        (_STD_AGENTS_TMP / (no + ".role.md")).write_text(
            _r.role_card(no, name, duties, pos, type_, (), tags=tags), encoding="utf-8")
    config.AGENTS_DIR = _STD_AGENTS_TMP


def tearDownModule():
    global _OLD_AGENTS
    config.AGENTS_DIR = _OLD_AGENTS
    import shutil as _sh
    _sh.rmtree(_STD_AGENTS_TMP, ignore_errors=True)


class TestNoHeadless(unittest.TestCase):
    def test_no_headless_channel(self):
        self.assertFalse(hasattr(agent, "run_headless"), "agent 模块不应再有 run_headless")
        self.assertFalse(hasattr(agent, "bash_exe"), "agent 模块不应再有 bash_exe")

    def test_preset_channel_is_gone(self):
        """preset 通道已移除：subagent 工具无 preset 参数，继承方向也反了，留着只会误导。"""
        for gone in ("PRESET_SRC", "PRESET_HOME", "role_preset", "preset_meta"):
            self.assertFalse(hasattr(agent, gone), "agent 不应再有 %s" % gone)

    def test_role_cards_exist(self):
        for n in range(1, 8):
            card = config.AGENTS_DIR / ("R%d.role.md" % n)
            self.assertTrue(card.exists(), "角色卡 R%d.role.md 应存在" % n)


class TestPromptInjection(unittest.TestCase):
    def test_agent_prompt_contains_task_and_tail(self):
        p = agent.agent_prompt("R6", "测试任务：更新 PRD 设计稿",
                               "工作区/产品设计师/T-001-S1.md", "工作区/产品设计师/T-001-S1.meta.json")
        self.assertIn("测试任务：更新 PRD 设计稿", p)
        self.assertIn("T-001-S1.md", p)
        self.assertIn("status 改为", p)
        self.assertIn("工作根目录", p)

    def test_agent_prompt_uses_role_card(self):
        p = agent.agent_prompt("R6", "x")
        self.assertIn("产品设计师", p)


class TestSubtaskSpec(unittest.TestCase):
    def test_spec_shape(self):
        spec = agent.subtask_spec("R2", "挖掘 5 条新用户原声", "期望：原声库增量", sub_no="T-007-S1")
        self.assertEqual(spec["role"], "R2")
        self.assertEqual(spec["roleName"], "需求研究员")
        self.assertNotIn("preset", spec)
        # 工作区目录自 2026-09-10 起统一为「R<n>（角色名）」，便于按编号排序与辨识
        self.assertEqual(spec["output"], "工作区/R2（需求研究员）/T-007-S1-report.md")
        self.assertEqual(spec["meta"], "工作区/R2（需求研究员）/T-007-S1.meta.json")
        self.assertIn("挖掘 5 条新用户原声", spec["prompt"])


class TestRoleSkills(unittest.TestCase):
    """C 路线技能装配：技能 md 平铺共享在 agents/skills/，角色卡「## 技能」段登记即装配。"""

    def _env(self, suffix):
        from pathlib import Path
        import shutil
        tmp = Path(__file__).resolve().parent.parent / (".skilltest-" + suffix)
        shutil.rmtree(tmp, ignore_errors=True)
        agents = tmp / "agents"
        (agents / "skills").mkdir(parents=True)
        old = config.AGENTS_DIR
        config.AGENTS_DIR = agents
        return tmp, agents, old

    def test_skills_from_shared_library_by_card_list(self):
        tmp, agents, old = self._env("shared")
        try:
            # 共享技能库：平铺，多角色可复用
            (agents / "skills" / "design-guide.md").write_text("## 设计规范\n- 主色用品牌蓝 #2563EB", encoding="utf-8")
            (agents / "skills" / "copy-guide.md").write_text("只属于内容岗的文案技能", encoding="utf-8")
            (agents / "R6.role.md").write_text(
                "# OPC 角色卡：R6 产品设计师\n\n## 职责\n- 设计\n\n## 技能\n- design-guide.md", encoding="utf-8")
            (agents / "R3.role.md").write_text(
                "# OPC 角色卡：R3 内容工厂\n\n## 职责\n- 内容\n\n## 技能\n- copy-guide.md", encoding="utf-8")
            p = agent.agent_prompt("R6", "做一版首页", "工作区/产品设计师/T-1-S1.md", "工作区/产品设计师/T-1-S1.meta.json")
            self.assertIn("【装配技能】", p)
            self.assertIn("设计规范", p)
            self.assertNotIn("只属于内容岗", p)       # 卡上没登记就不装
            p2 = agent.agent_prompt("R3", "写一条推文")  # R3 装自己的
            self.assertIn("只属于内容岗", p2)
            self.assertNotIn("品牌蓝", p2)
        finally:
            config.AGENTS_DIR = old
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_skill_file_and_empty_card_are_noops(self):
        tmp, agents, old = self._env("empty")
        try:
            (agents / "R2.role.md").write_text("# OPC 角色卡：R2\n\n## 职责\n- 调研", encoding="utf-8")   # 无技能段
            (agents / "R3.role.md").write_text(
                "# OPC 角色卡：R3\n\n## 职责\n- 内容\n\n## 技能\n- 不存在.md\n- （未装配提示行不算）", encoding="utf-8")
            self.assertNotIn("【装配技能】", agent.agent_prompt("R2", "普通任务"))
            p3 = agent.agent_prompt("R3", "普通任务")   # 登记了但库文件不存在 / 提示行 → 不注入
            self.assertNotIn("【装配技能】", p3)
        finally:
            config.AGENTS_DIR = old
            shutil.rmtree(tmp, ignore_errors=True)



if __name__ == "__main__":
    unittest.main(verbosity=2)