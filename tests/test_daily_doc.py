# -*- coding: utf-8 -*-
"""模型输出 → 落盘文档的通解：归一化 + 落盘前结构校验。

两次真实事故都是「模型把交付物当回复内容写」：
  09-11：前置说明行 + 围栏；
  09-14：前置说明行 + 围栏 + 结尾「处理说明」段。
修法不是把包装写法列举全（补不完），而是：归一化按结构取正文 + 落盘前校验不合格就兜底。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import scheduler as S  # noqa: E402

NL = chr(10)
F = chr(96) * 3          # 三个反引号（写成常量，免得本文件自己被当成围栏）


class TestAsDocument(unittest.TestCase):
    def test_plain_document_untouched(self):
        doc = "# 每日简报 · 2026-09-14" + NL + "正文" + NL
        self.assertEqual(S._as_document(doc).strip(), doc.strip())

    def test_strips_preamble_and_fence(self):
        """09-11 那种：前置说明 + 整篇塞进围栏。"""
        wrapped = ("合并后的完整简报（已写入 xxx）：" + NL + NL
                   + F + "markdown" + NL + "# 每日简报 · 2026-09-14" + NL + "正文" + NL + F + NL)
        self.assertEqual(S._as_document(wrapped).splitlines()[0], "# 每日简报 · 2026-09-14")
        self.assertNotIn(F, S._as_document(wrapped))

    def test_strips_trailing_commentary_after_fence(self):
        """09-14 那种：围栏闭合之后还跟着一段「处理说明」。"""
        wrapped = ("说明：" + NL + F + NL + "# 每日简报 · 2026-09-14" + NL + "正文" + NL + F + NL
                   + "处理说明：" + NL + "- 一" + NL + "- 二" + NL)
        out = S._as_document(wrapped)
        self.assertEqual(out.splitlines()[0], "# 每日简报 · 2026-09-14")
        self.assertNotIn("处理说明", out)

    def test_long_preamble_is_not_size_limited(self):
        """前置说明可以很长 —— 老实现只在前 6 行里找标题，说明一长就漏。"""
        wrapped = NL.join(["很长的说明 %d" % i for i in range(20)]) + NL + "# 每日简报 · 2026-09-14" + NL + "正文"
        self.assertEqual(S._as_document(wrapped).splitlines()[0], "# 每日简报 · 2026-09-14")

    def test_body_code_block_is_preserved(self):
        """正文自带的代码块是内容，不许被当成收尾围栏截掉。"""
        doc = "# 每日简报 · 2026-09-14" + NL + "看：" + NL + F + NL + "code" + NL + F + NL + "结束" + NL
        self.assertIn("code", S._as_document(doc))

    def test_fenced_doc_with_inner_code_block_keeps_the_block(self):
        wrapped = ("说明" + NL + F + "md" + NL + "# 每日简报 · 2026-09-14" + NL + "看：" + NL
                   + F + NL + "code" + NL + F + NL + "结束" + NL + F + NL + "处理说明" + NL)
        out = S._as_document(wrapped)
        self.assertIn("code", out)
        self.assertNotIn("处理说明", out)

    def test_idempotent(self):
        for s in ("# A" + NL + "x", "前" + NL + F + NL + "# A" + NL + "x" + NL + F + NL + "尾"):
            once = S._as_document(s)
            self.assertEqual(S._as_document(once), once)

    def test_no_title_returned_as_is(self):
        self.assertEqual(S._as_document("就是一段话"), "就是一段话")


class TestDocOk(unittest.TestCase):
    def test_accepts_clean_doc(self):
        self.assertTrue(S._doc_ok("# 每日简报 · 2026-09-14" + NL + "x", "每日简报", "2026-09-14"))

    def test_rejects_wrapped_text(self):
        wrapped = "合并后的完整简报（已覆写 x）：" + NL + F + NL + "# 每日简报 · 2026-09-14" + NL + F
        self.assertFalse(S._doc_ok(wrapped, "每日简报", "2026-09-14"))

    def test_rejects_wrong_date_or_empty(self):
        self.assertFalse(S._doc_ok("# 每日简报 · 2026-09-13", "每日简报", "2026-09-14"))
        self.assertFalse(S._doc_ok("", "每日简报", "2026-09-14"))
        self.assertFalse(S._doc_ok("## 今天干了什么", "每日简报", "2026-09-14"))


if __name__ == "__main__":
    unittest.main()
