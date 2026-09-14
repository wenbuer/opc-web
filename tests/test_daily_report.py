# -*- coding: utf-8 -*-
"""每日简报增量合并自检（纯标准库 unittest，不依赖模型与真实项目）：
_merge_daily 强制保留历史任务段落 / _daily_fallback 代码级合并不盲目追加。
运行：python -m unittest tests.test_daily_report -v  （在 opc-web/ 下）。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, scheduler, templates  # noqa: E402


OLD = """# 每日简报 · 2026-09-07

## 当日概况
- 任务：今日完成 T-001（PRD 落地）

## 按任务分组的进展与结论

### T-001｜需求拆解
**结论**：完成（2/2）。
- R2 产品需求（完成）：产出 PRD 初稿

## 知识库沉淀
- 新建：知识库/产品/KeepTalk-APP.md

## 待办 / 风险提示
**风险**：无
**待办**：无
"""


class TestDailyMerge(unittest.TestCase):
    """_merge_daily：模型合并稿的历史段落强制逐字保留。"""

    def test_merge_keeps_history_verbatim(self):
        new = OLD.replace("产出 PRD 初稿", "产出 PRD（被模型改写）").replace(
            "- 任务：今日完成 T-001（PRD 落地）",
            "- 任务：今日完成 T-001（PRD 落地）、T-002（首页设计）")
        merged = scheduler._merge_daily(OLD, new, "T-002")
        self.assertIn("### T-001｜需求拆解", merged)
        self.assertIn("产出 PRD 初稿", merged)          # 原文被回填，模型改写无效
        self.assertNotIn("被模型改写", merged)
        self.assertIn("T-002", merged)                  # 新任务段落保留

    def test_merge_rejects_lost_history(self):
        new = OLD.replace("### T-001｜需求拆解", "### T-001X｜需求拆解")   # 结构被改 → 历史丢失
        self.assertEqual(scheduler._merge_daily(OLD, new, "T-002"), "")

    def test_merge_same_task_may_update(self):
        new = OLD.replace("产出 PRD 初稿", "产出 PRD 终稿")
        merged = scheduler._merge_daily(OLD, new, "T-001")
        self.assertIn("产出 PRD 终稿", merged)          # 本次任务自己的段落允许更新（重跑=更新）


class TestDailyFallback(unittest.TestCase):
    """_daily_fallback：模型不可用时的代码级合并。"""

    def test_fallback_inserts_block_and_keeps_old(self):
        reps = [{"task_no": "T-002", "role": "R3 全栈开发", "status": "完成",
                 "body": "实现了可运行首页。", "date": "2026-09-07"}]
        out = scheduler._daily_fallback(OLD, reps, "T-002", "2026-09-07")
        self.assertIn("### T-001｜需求拆解", out)                    # 旧段落原样
        self.assertIn("### T-002｜自动合并", out)                    # 新段落已插入
        self.assertIn("- 任务：合并 T-002", out)                     # 概况补一行
        self.assertLess(out.index("### T-001"), out.index("### T-002"))

    def test_fallback_same_task_updates_block(self):
        reps = [{"task_no": "T-001", "role": "R2 产品需求", "status": "完成",
                 "body": "PRD 更新版。", "date": "2026-09-07"}]
        out = scheduler._daily_fallback(OLD, reps, "T-001", "2026-09-07")
        self.assertIn("### T-001｜自动合并", out)
        self.assertEqual(out.count("### T-001"), 1)     # 同任务重跑：更新段落，不重复追加

    def test_fallback_first_daily_skeleton(self):
        reps = [{"task_no": "T-001", "role": "R2", "status": "完成", "body": "x", "date": "d"}]
        out = scheduler._daily_fallback("", reps, "T-001", "2026-09-08")
        for sec in ("## 当日概况", "## 按任务分组的进展与结论", "## 知识库沉淀", "## 待办 / 风险提示"):
            self.assertIn(sec, out)


class TestBuildDailyReport(unittest.TestCase):
    """build_daily_report 端到端（mock 台账与模型，落 tmp 批阅台，不碰真实项目）。"""

    def setUp(self):
        import shutil
        self._root = Path(__file__).resolve().parent.parent / (".testroot-daily-%d" % id(self))
        import shutil as _sh
        _sh.rmtree(self._root, ignore_errors=True)
        (self._root / "批阅台").mkdir(parents=True)
        self._old = (config.ROOT, config.BATCH_ROOT, scheduler.store, scheduler._headless_text)
        config.ROOT = self._root                       # 生产中 BATCH_ROOT 恒为 ROOT 子目录，测试同拓扑
        config.BATCH_ROOT = self._root / "批阅台"

    def tearDown(self):
        config.ROOT, config.BATCH_ROOT, scheduler.store, scheduler._headless_text = self._old
        import shutil
        shutil.rmtree(self._root, ignore_errors=True)

    @staticmethod
    def _reps():
        return [{"task_no": "T-002", "role": "R3", "status": "完成",
                 "body": "首页完成", "date": "2026-09-07"}]

    def test_model_draft_merged_with_history_guard(self):
        import types
        scheduler.store = types.SimpleNamespace(reports=lambda task_no=None: self._reps())
        draft = OLD.replace("## 知识库沉淀",           # 模型稿：T-001 段落原样 + 新增 T-002 段
                            "### T-002｜首页设计\n**结论**：完成。\n- R3（完成）：首页完成\n\n## 知识库沉淀")
        scheduler._headless_text = lambda prompt, timeout=600: draft
        target = config.BATCH_ROOT / "每日简报-2026-09-07.md"
        target.write_text(OLD, encoding="utf-8")       # 预置当天已有简报
        out = scheduler.build_daily_report("T-002", "2026-09-07")
        self.assertTrue(out["merged"])
        text = target.read_text(encoding="utf-8")
        self.assertIn("产出 PRD 初稿", text)           # 历史任务段落保留
        self.assertIn("### T-002｜首页设计", text)      # 本次任务段落并入

    def test_model_fail_falls_back(self):
        import types
        scheduler.store = types.SimpleNamespace(reports=lambda task_no=None: self._reps())
        scheduler._headless_text = lambda prompt, timeout=600: ""     # 模型不可用
        target = config.BATCH_ROOT / "每日简报-2026-09-07.md"
        target.write_text(OLD, encoding="utf-8")
        out = scheduler.build_daily_report("T-002", "2026-09-07")
        self.assertTrue(out["merged"])
        text = target.read_text(encoding="utf-8")
        self.assertIn("### T-002｜自动合并", text)      # 代码级合并兜底
        self.assertIn("### T-001｜需求拆解", text)      # 旧内容未动

    def test_no_reps_skips(self):
        import types
        scheduler.store = types.SimpleNamespace(reports=lambda task_no=None: [])
        out = scheduler.build_daily_report("T-009", "2026-09-07")
        self.assertFalse(out["merged"])
        self.assertFalse((config.BATCH_ROOT / "每日简报-2026-09-07.md").exists())


class TestDocTemplates(unittest.TestCase):
    """doc_template：三种文书模板非空且含关键锚点；未知 kind 报错。"""

    def test_three_templates_present(self):
        cases = {"回报产出": ("## 结论", "## 需要 R0 拍板", "## 小任务合并规则"),
                 "决策建议": ("## 决策点", "## 现状背景", "## 建议", "## 拍板后动作", "## 附注"),
                 "每日简报": ("## 当日概况", "## 按任务分组的进展与结论", "## 知识库沉淀", "## 待办 / 风险提示")}
        for kind, marks in cases.items():
            t = templates.doc_template(kind)
            self.assertTrue(t.strip(), kind)
            for m in marks:
                self.assertIn(m, t, kind)

    def test_unknown_kind_raises(self):
        with self.assertRaises(KeyError):
            templates.doc_template("不存在的模板")


if __name__ == "__main__":
    unittest.main()
