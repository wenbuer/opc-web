# -*- coding: utf-8 -*-
"""ApiEngine：直连 API 的 agent 循环（工具调用 / 沙箱 / 进度 / 用量 / 取消）。

网络层用 mock 替换（_stream_chat），只验证编排逻辑；真实调用由手工端到端验证。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config  # noqa: E402
from opc_web.engines import api as E  # noqa: E402


class TestSandbox(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="apieng-"))
        self._old = config.ROOT
        config.ROOT = self._tmp
        (self._tmp / "项目").mkdir()

    def tearDown(self):
        config.ROOT = self._old
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_safe_path_inside_root(self):
        p = E._safe_path("项目/a.txt")
        self.assertTrue(str(p).startswith(str(self._tmp)))

    def test_safe_path_rejects_escape(self):
        for bad in ("../outside.txt", "项目/../../x", "C:/Windows/system.ini"):
            with self.assertRaises(ValueError, msg=bad):
                E._safe_path(bad)

    def test_write_then_read(self):
        msg = E._t_write_file({"path": "项目/产出.txt", "content": "你好"})
        self.assertIn("已写入", msg)
        self.assertEqual(E._t_read_file({"path": "项目/产出.txt"}), "你好")

    def test_list_dir(self):
        (self._tmp / "项目" / "a.txt").write_text("x", encoding="utf-8")
        out = E._t_list_dir({"path": "项目"})
        self.assertIn("a.txt", out)


class TestAgentLoop(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="apiloop-"))
        self._old = config.ROOT
        config.ROOT = self._tmp

    def tearDown(self):
        config.ROOT = self._old
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_single_turn_text(self):
        with mock.patch.object(E, "_stream_chat",
                               return_value={"text": "干完了", "tool_calls": [], "finish": "stop",
                                             "usage": {"inputTokens": 11, "outputTokens": 3,
                                                       "cacheReadTokens": 0, "reasoningTokens": 0}}):
            res = E.ApiEngine().run("随便", timeout=30, act="T-1-S1")
        self.assertEqual(res.text, "干完了")
        self.assertEqual(res.usage["inputTokens"], 11)
        self.assertTrue(res.ok())

    def test_tool_call_then_text(self):
        calls = []

        def fake(cfg, messages, on_delta=None, cancel=None):
            calls.append(list(messages))
            if len(calls) == 1:
                return {"text": "", "finish": "tool_calls", "usage": None,
                        "tool_calls": [{"id": "c1", "name": "write_file",
                                        "arguments": json.dumps({"path": "out.txt", "content": "证据"},
                                                                ensure_ascii=False)}]}
            return {"text": "已写入并回报", "tool_calls": [], "finish": "stop",
                    "usage": {"inputTokens": 5, "outputTokens": 4, "cacheReadTokens": 0, "reasoningTokens": 0}}

        seen = []
        with mock.patch.object(E, "_stream_chat", side_effect=fake):
            res = E.ApiEngine().run("写个文件", timeout=30, act="T-2-S1",
                                    on_progress=lambda p: seen.append(p))
        self.assertEqual(res.text, "已写入并回报")
        self.assertEqual((self._tmp / "out.txt").read_text(encoding="utf-8"), "证据")
        # 第二轮的消息里应带上工具执行结果
        second = calls[1]
        self.assertTrue(any(m.get("role") == "tool" and "已写入" in str(m.get("content")) for m in second))
        self.assertTrue(seen, "应回调进度")
        self.assertGreaterEqual(seen[-1].tools, 1)

    def test_max_steps_stops(self):
        def always_tool(cfg, messages, on_delta=None, cancel=None):
            return {"text": "", "finish": "tool_calls", "usage": None,
                    "tool_calls": [{"id": "c", "name": "list_dir", "arguments": "{}"}]}

        with mock.patch.object(E, "_stream_chat", side_effect=always_tool):
            with mock.patch.object(E, "_cfg", return_value=dict(E._DEFAULTS, maxSteps=3)):
                res = E.ApiEngine().run("空转", timeout=30, act="T-3-S1")
        self.assertIn("循环上限", res.error)

    def test_cancel_stops(self):
        eng = E.ApiEngine()

        def slow(cfg, messages, on_delta=None, cancel=None):
            if cancel and cancel():
                return {"text": "", "tool_calls": [], "finish": "cancelled", "usage": None}
            return {"text": "", "finish": "tool_calls", "usage": None,
                    "tool_calls": [{"id": "c", "name": "list_dir", "arguments": "{}"}]}

        with mock.patch.object(E, "_stream_chat", side_effect=slow):
            eng.kill("T-4-S1")     # 先置取消标志
            res = eng.run("会被取消", timeout=30, act="T-4-S1")
        self.assertTrue(res.killed)

    def test_missing_key_returns_error(self):
        with mock.patch.object(E, "_api_key", return_value=""):
            res = E.ApiEngine().run("x", timeout=5, act="")
        self.assertIn("API Key", res.error)


if __name__ == "__main__":
    unittest.main()
