# -*- coding: utf-8 -*-
"""dsh 用量口径：逐轮累加。

每条 assistant/message 的 usage 是「该轮」的量，不是会话累计值 —— 只取最后一条会
漏掉前面所有轮次（实测一次 9 轮任务：174k 输入被记成 26k），而 api 引擎是逐轮累加的，
两个引擎的数字就再也比不了。
"""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import zstandard as zstd  # noqa: E402

from opc_web.engines import dsh as edsh  # noqa: E402


def _session(evs, name="session.v3.jsonl.zstd"):
    d = Path(__file__).resolve().parent.parent / (".testusg-%d-%s" % (os.getpid(), id(evs)))
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    raw = ("\n".join(json.dumps(e, ensure_ascii=False) for e in evs)).encode("utf-8")
    with open(d / name, "wb") as fh:
        fh.write(zstd.ZstdCompressor().compress(raw))
    return d


def _msg(step, i, c, o, r=0):
    return {"type": "assistant/message", "seq": step,
            "data": {"step": step, "usage": {"inputTokens": i, "cacheReadTokens": c,
                                             "outputTokens": o, "reasoningTokens": r}}}


class TestDshUsage(unittest.TestCase):
    def test_sums_every_turn(self):
        d = _session([{"type": "session", "cwd": "x"}, _msg(1, 4975, 7680, 197, 10),
                      _msg(2, 2195, 12800, 119), _msg(3, 256, 26240, 443, 5)])
        try:
            u = edsh._usage_from_session(d)
            self.assertEqual(4975 + 2195 + 256, u["inputTokens"])
            self.assertEqual(7680 + 12800 + 26240, u["cacheReadTokens"])
            self.assertEqual(197 + 119 + 443, u["outputTokens"])
            self.assertEqual(15, u["reasoningTokens"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_single_turn_unchanged(self):
        d = _session([_msg(1, 4706, 7936, 213, 166)])
        try:
            self.assertEqual({"inputTokens": 4706, "outputTokens": 213,
                              "cacheReadTokens": 7936, "reasoningTokens": 166},
                             edsh._usage_from_session(d))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_legacy_chunk_takes_last(self):
        """旧格式（只有 assistant/chunk 的 usage）保持原语义：取最后一条。"""
        evs = [{"type": "assistant/chunk", "data": {"chunk": {"type": "usage", "usage": {"inputTokens": 10, "outputTokens": 1}}}},
               {"type": "assistant/chunk", "data": {"chunk": {"type": "usage", "usage": {"inputTokens": 99, "outputTokens": 9}}}}]
        d = _session(evs, name="session.jsonl.zstd")
        try:
            u = edsh._usage_from_session(d)
            self.assertEqual(99, u["inputTokens"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_old_log_name_still_read(self):
        d = _session([_msg(1, 5, 6, 7)], name="session.jsonl.zstd")
        try:
            self.assertEqual(5, edsh._usage_from_session(d)["inputTokens"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
