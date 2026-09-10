# -*- coding: utf-8 -*-
"""执行引擎接口：注册表选择、能力声明、runner 委托、配置错误不静默回退。

对应 docs/引擎解耦设计.md 阶段 1——上层只依赖 runner 的既有签名，
引擎是谁由配置决定（opc-config.json 的 engine / OPC_ENGINE）。
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, engines, runner  # noqa: E402
from opc_web.engines import base as ebase  # noqa: E402


class FakeEngine(ebase.Engine):
    name = "fake"

    def capabilities(self):
        return {"tools": True, "streaming": False, "usage": True, "skills": False, "sandbox": False}

    def run(self, prompt, *, timeout=600, act="", cwd=None, on_progress=None):
        if on_progress:
            on_progress(ebase.Progress(alive=True, elapsed=3, tools=2, lastTool="pwsh ls"))
        return ebase.RunResult(text="假引擎文本", usage={"inputTokens": 10, "outputTokens": 2,
                                                       "cacheReadTokens": 0, "reasoningTokens": 0},
                               session="fake-1", elapsed=1.5)


class TestRegistry(unittest.TestCase):
    def test_dsh_registered(self):
        self.assertIn("dsh", engines.available())

    def test_get_engine_by_name(self):
        e = engines.get_engine("dsh")
        self.assertEqual(e.name, "dsh")
        cap = e.capabilities()
        for k in ("tools", "streaming", "usage", "skills", "sandbox"):
            self.assertIn(k, cap)

    def test_default_follows_config(self):
        with mock.patch.object(config, "ENGINE", "dsh"):
            self.assertEqual(engines.get_engine().name, "dsh")

    def test_unknown_engine_raises(self):
        # 写错引擎名必须报错（静默回退会掩盖配置错误）
        with self.assertRaises(ebase.EngineError):
            engines.get_engine("no-such-engine")

    def test_preflight_returns_tuple(self):
        ok, msg = engines.get_engine("dsh").preflight()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)


class TestRunnerDelegates(unittest.TestCase):
    """runner 的公开函数只依赖引擎接口，不再直接调 dsh。"""

    def test_run_headless_task_uses_engine(self):
        with mock.patch("opc_web.engines.registry._ENGINES", {"fake": FakeEngine}):
            with mock.patch.object(config, "ENGINE", "fake"):
                text, usage = runner.run_headless_task("任意 prompt", timeout=5, act="T-1-S1")
        self.assertEqual(text, "假引擎文本")
        self.assertEqual(usage["inputTokens"], 10)

    def test_run_headless_sync_uses_engine(self):
        with mock.patch("opc_web.engines.registry._ENGINES", {"fake": FakeEngine}):
            with mock.patch.object(config, "ENGINE", "fake"):
                self.assertEqual(runner.run_headless_sync("任意 prompt", timeout=5), "假引擎文本")

    def test_kill_spawn_delegates(self):
        called = {}

        class KillEngine(FakeEngine):
            name = "kill"

            def kill(self, act):
                called["act"] = act
                return True

        with mock.patch("opc_web.engines.registry._ENGINES", {"kill": KillEngine}):
            with mock.patch.object(config, "ENGINE", "kill"):
                self.assertTrue(runner.kill_spawn("T-9-S1"))
        self.assertEqual(called["act"], "T-9-S1")


if __name__ == "__main__":
    unittest.main()
