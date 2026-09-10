# -*- coding: utf-8 -*-
"""每日简报：抽象摘要结构 + 增量合并校验（纯标准库 unittest，不依赖模型与真实项目）。

结构自 2026-09-10 起改为「今天干了什么 + 一行一任务」——旧结构按任务分节、
且要求模型逐字保留历史段落，导致简报只增不减（曾膨胀到 51 KB）。
运行：python -m unittest tests.test_daily_report -v  （在 opc-web/ 下）。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, scheduler, templates  # noqa: E402


OLD = """# 每日简报 · 2026-09-07

## 今天干了什么
需求拆解完成，首版 PRD 落地。

## 完成任务
- T-001｜需求拆解与 PRD 落地（R2）

## 待 R0 拍板
无

## 风险与待办
**风险**：无
**待办**：无
"""


class TestDailyBlocks(unittest.TestCase):
    def test_parses_task_lines(self):
        got = scheduler._daily_task_blocks(OLD)
        self.assertIn("T-001", got)
        self.assertTrue(got["T-001"].startswith("- T-001｜"))

    def test_empty_when_no_section(self):
        self.assertEqual(scheduler._daily_task_blocks("# 每日简报\n没有小节"), {})


class TestDailyMerge(unittest.TestCase):
    """_merge_daily：只守「任务号不丢」，允许模型压缩改写（这是简报能瘦下来的前提）。"""

    def test_allows_compression(self):
        new = OLD.replace("需求拆解与 PRD 落地（R2）", "需求拆解").replace(
            "需求拆解完成，首版 PRD 落地。", "完成需求拆解。")
        merged = scheduler._merge_daily(OLD, new, "T-002")
        self.assertIn("完成需求拆解。", merged)          # 压缩后的写法被接受
        self.assertIn("- T-001｜需求拆解", merged)

    def test_rejects_lost_task(self):
        new = OLD.replace("- T-001｜需求拆解与 PRD 落地（R2）", "- T-001X｜别的")
        self.assertEqual(scheduler._merge_daily(OLD, new, "T-002"), "")

    def test_new_task_kept(self):
        new = OLD.replace("- T-001｜需求拆解与 PRD 落地（R2）",
                          "- T-001｜需求拆解\n- T-002｜首页设计稿")
        merged = scheduler._merge_daily(OLD, new, "T-002")
        self.assertIn("T-002", merged)


class TestDailyFallback(unittest.TestCase):
    """_daily_fallback：模型不可用时的代码级合并，每个任务一行。"""

    def test_fallback_appends_one_line(self):
        reps = [{"task_no": "T-002", "role": "R3", "status": "完成",
                 "body": "实现了可运行首页。", "date": "2026-09-07"}]
        out = scheduler._daily_fallback(OLD, reps, "T-002", "2026-09-07")
        self.assertIn("- T-001｜需求拆解与 PRD 落地（R2）", out)      # 旧的一行原样
        self.assertIn("- T-002｜", out)                              # 新任务一行
        self.assertLess(out.index("- T-001"), out.index("- T-002"))

    def test_fallback_same_task_updates_line(self):
        reps = [{"task_no": "T-001", "role": "R2", "status": "完成",
                 "body": "PRD 更新版。", "date": "2026-09-07"}]
        out = scheduler._daily_fallback(OLD, reps, "T-001", "2026-09-07")
        self.assertEqual(out.count("- T-001｜"), 1)                  # 重跑更新该行，不重复追加

    def test_fallback_first_daily_skeleton(self):
        reps = [{"task_no": "T-001", "role": "R2", "status": "完成", "body": "x", "date": "d"}]
        out = scheduler._daily_fallback("", reps, "T-001", "2026-09-08")
        for sec in ("## 今天干了什么", "## 完成任务", "## 待 R0 拍板", "## 风险与待办"):
            self.assertIn(sec, out)


class TestTemplate(unittest.TestCase):
    def test_template_has_new_sections(self):
        tpl = templates.doc_template("每日简报")
        for sec in ("## 今天干了什么", "## 完成任务", "## 待 R0 拍板", "## 风险与待办"):
            self.assertIn(sec, tpl)
        self.assertNotIn("## 按任务分组的进展与结论", tpl)

    def test_template_sets_size_limit(self):
        tpl = templates.doc_template("每日简报")
        self.assertIn("50 行", tpl)                                  # 抽象不下来的信号


if __name__ == "__main__":
    unittest.main()
