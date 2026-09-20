# -*- coding: utf-8 -*-
"""提示词契约：身份抬头 + JSON 输出契约只有一处出口。

原先 4 个调用点各写一遍「你是老板助理 R1」「只输出 JSON」+ 自己的超时和解析器，
改一处口径就漏另一处；身份还与角色卡（可在设置里改）各说各话。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, scheduler as S  # noqa: E402


class TestHeadlessJson(unittest.TestCase):
    def setUp(self):
        self._old_ht = S._headless_text
        self._old_rn = config.role_name
        self.seen = []

        def fake_ht(prompt, timeout=600, label=""):
            self.seen.append((prompt, timeout, label))
            return self.reply
        S._headless_text = fake_ht
        config.role_name = lambda no: "老板助理"
        self.reply = ""

    def tearDown(self):
        S._headless_text = self._old_ht
        config.role_name = self._old_rn

    def test_wraps_identity_and_json_contract(self):
        self.reply = '{"need": true}'
        d = S._headless_json("任务：X", 300)
        self.assertEqual(d, {"need": True})
        sent, timeout, label = self.seen[0]
        self.assertTrue(sent.startswith("你是老板助理 R1。 "), sent[:30])
        self.assertIn("任务：X", sent)
        self.assertIn("只输出 JSON", sent)
        self.assertEqual(timeout, 300)
        self.assertEqual(label, "", "未传 label 时留空，不硬编一个用途名")

    def test_identity_comes_from_the_role_card(self):
        """改角色名后 prompt 要跟着变 —— 写死就会与工作区目录名/界面脱节。"""
        config.role_name = lambda no: "首席助理"
        self.reply = "{}"
        S._headless_json("x")
        self.assertIn("你是首席助理 R1。", self.seen[0][0])

    def test_none_when_model_silent_or_unparseable(self):
        self.reply = ""
        self.assertIsNone(S._headless_json("x"))
        self.reply = "我觉得吧，还是算了"          # 没有 JSON
        self.assertIsNone(S._headless_json("x"))
        self.reply = "[1, 2]"                      # 顶层是数组：不是本契约的形状
        self.assertIsNone(S._headless_json("x"))

    def test_custom_parser_is_honoured(self):
        self.reply = "[]"
        got = S._headless_json("x", parser=lambda t: ["ok"], label="时间轴")
        self.assertEqual(got, ["ok"])
        self.assertEqual(self.seen[0][2], "时间轴", "label 要一路传到用量日志")


if __name__ == "__main__":
    unittest.main()
