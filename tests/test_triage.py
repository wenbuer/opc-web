# -*- coding: utf-8 -*-
"""决策分界线：只有角色在回报「## 需要 R0 拍板」小节里声明的事项才进决策裁决。

背景（两代错法）：① 宽关键词判定（含「是否/决定/方向/启动」）——回报里到处都有，
例行汇报被整片推成待决；② 扫「需要拍板」字样取后文——把角色正文的泛指句子抓成声明
（T-007 曾把 R4 的 UI 描述当成待拍板内容）。现改为结构化小节 + 模板准入清单。
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import scheduler, templates  # noqa: E402

WITH_SECTION = """## 结论
已完成。

## 需要 R0 拍板
**决策点 1：运行方式是否按「可编辑安装」定稿？**
- 我的建议：选 A。
"""

WITH_EMPTY_SECTION = """## 结论
已完成。

## 需要 R0 拍板
无

## 风险与未尽事项
无
"""

NO_SECTION = """## 结论
完成了首页接线，产出已落盘。

## 产出清单
| 产出 | 路径 |
|---|---|
| a | b |
"""

MENTION_ONLY = """## 依据与要点
- 本处提到「需要 R0 拍板」的字样，但并没有那一个小节。
"""


class TestPendingItems(unittest.TestCase):
    def test_section_present_means_decision(self):
        got = scheduler._pending_items([{"role": "R3", "body": WITH_SECTION}])
        self.assertIn("运行方式", got)
        self.assertIn("【R3】", got)

    def test_empty_section_means_report_only(self):
        self.assertEqual(scheduler._pending_items([{"role": "R3", "body": WITH_EMPTY_SECTION}]), "")

    def test_no_section_means_report_only(self):
        self.assertEqual(scheduler._pending_items([{"role": "R3", "body": NO_SECTION}]), "")

    def test_mere_mention_does_not_count(self):
        # 只提到字样、没有小节 → 不算声明（旧错法会在这里误判）
        self.assertEqual(scheduler._pending_items([{"role": "R4", "body": MENTION_ONLY}]), "")

    def test多角色拼接(self):
        got = scheduler._pending_items([
            {"role": "R3", "body": WITH_SECTION},
            {"role": "R4", "body": "## 需要 R0 拍板\n**决策点：账号体系进不进 MVP？**"},
        ])
        self.assertIn("【R3】", got)
        self.assertIn("【R4】", got)
        self.assertIn("账号体系", got)


class TestAdviceSummary(unittest.TestCase):
    def test_returns_model_text(self):
        with mock.patch.object(scheduler, "_headless_text",
                               return_value="## 决策点\n选 A 还是 B？"):
            got = scheduler._advice_summary([{"role": "R3", "body": WITH_SECTION}], "任务")
        self.assertIn("决策点", got)

    def test_empty_when_model_silent(self):
        with mock.patch.object(scheduler, "_headless_text", return_value=""):
            got = scheduler._advice_summary([{"role": "R3", "body": WITH_SECTION}], "任务")
        self.assertEqual(got, "")


class TestTemplateCarriesBoundary(unittest.TestCase):
    def test_report_template_has_admission_list(self):
        tpl = templates.doc_template("回报产出")
        self.assertIn("准入清单", tpl)
        self.assertIn("后续动作", tpl)
        self.assertIn("最多 2 条", tpl)

    def test_advice_template_documents_boundary(self):
        tpl = templates.doc_template("决策建议")
        self.assertIn("分界线", tpl)
        self.assertIn("干不下去", tpl)


if __name__ == "__main__":
    unittest.main()
