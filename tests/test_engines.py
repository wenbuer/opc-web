# -*- coding: utf-8 -*-
"""执行引擎接口：注册表选择、能力声明、runner 委托、配置错误不静默回退。

对应 docs/引擎解耦设计.md 阶段 1——上层只依赖 runner 的既有签名，
引擎是谁由配置决定（opc-config.json 的 engine / OPC_ENGINE）。
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, engines, runner  # noqa: E402
from opc_web.engines import base as ebase  # noqa: E402
from opc_web.engines import registry as ereg  # noqa: E402


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


class TestDefaultEngine(unittest.TestCase):
    @unittest.skipIf(os.environ.get("OPC_ENGINE"), "OPC_ENGINE 覆盖了默认值")
    def test_default_is_api(self):
        """默认引擎是直连 API（不依赖 dsh）；dsh 作为可选项保留。"""
        self.assertEqual(str(config.ENGINE), "api")


class TestDescribe(unittest.TestCase):
    """设置页引擎区依赖的自述接口：当前是谁、能不能用、有什么能力。"""

    def test_lists_both_engines(self):
        d = engines.describe()
        names = [e["name"] for e in d["engines"]]
        self.assertIn("api", names)
        self.assertIn("dsh", names)
        self.assertIn(d["current"], names)
        self.assertEqual(sum(1 for e in d["engines"] if e["current"]), 1)   # 只有一个「当前」

    def test_each_engine_self_describes(self):
        for e in engines.describe()["engines"]:
            self.assertTrue(e["label"])
            self.assertTrue(e["description"])
            self.assertIn("ok", e)          # preflight 结果必须给出来，不能只在派发时才发现不可用
            self.assertIsInstance(e["note"], str)

    def test_load_errors_exported(self):
        self.assertIsInstance(engines.load_errors(), dict)   # 包根必须导出（server 直接 import）

    def test_load_failure_is_recorded_not_swallowed(self):
        with mock.patch("importlib.import_module", side_effect=RuntimeError("内置模块坏了")):
            with mock.patch.dict(ereg._ENGINES, {}, clear=True):
                with mock.patch.dict(ereg._LOAD_ERRORS, {}, clear=True):
                    errs = engines.load_errors()
                    self.assertTrue(errs, "导入失败必须记录在案")
                    with self.assertRaises(ebase.EngineError):
                        engines.get_engine("dsh")


class TestProgressSink(unittest.TestCase):
    """进度通道统一：引擎的 on_progress 落到 _EXEC_STATE（dsh 与 api 共用一条路）。"""

    def test_sink_writes_state(self):
        sink = runner._progress_sink("T-77-S1")
        sink(ebase.Progress(alive=True, elapsed=4, tools=3, lastTool="read_file a.md",
                            lastText="正在读", session="sess-123456789012"))
        try:
            st = runner.exec_state()["T-77-S1"]
            self.assertEqual(st["tools"], 3)
            self.assertEqual(st["lastTool"], "read_file a.md")
            self.assertEqual(st["session"], "sess-123456789012")
        finally:
            runner._EXEC_STATE.pop("T-77-S1", None)

    def test_sink_without_act_is_none(self):
        self.assertIsNone(runner._progress_sink(""))      # 无子任务号的同步直跑不记状态

    def test_engine_progress_reaches_state(self):
        """真实路径：run_headless_task 把回调接上，引擎报的进度进得了 exec_state。"""
        with mock.patch("opc_web.engines.registry._ENGINES", {"fake": FakeEngine}):
            with mock.patch.object(config, "ENGINE", "fake"):
                runner.run_headless_task("任意 prompt", timeout=5, act="T-78-S1")
        try:
            self.assertEqual(runner.exec_state()["T-78-S1"]["tools"], 2)   # FakeEngine 报 tools=2
        finally:
            runner._EXEC_STATE.pop("T-78-S1", None)


class TestApiEngineConfig(unittest.TestCase):
    """api 引擎沿用「设置 → 模型接入」的配置，而不是另有一份。"""

    def test_cfg_follows_model_section(self):
        from opc_web.engines import api as eapi
        section = {"provider": "custom", "baseURL": "https://example.test/v1",
                   "model": "my-model", "apiKeyEnv": "CUSTOM_API_KEY"}
        with mock.patch.dict(config._CFG, {"model": section, "engines": {}}):
            cfg = eapi._cfg()
        self.assertEqual(cfg["baseUrl"], "https://example.test/v1")
        self.assertEqual(cfg["model"], "my-model")
        self.assertEqual(cfg["apiKeyEnv"], "CUSTOM_API_KEY")

    def test_engines_section_overrides_model(self):
        from opc_web.engines import api as eapi
        with mock.patch.dict(config._CFG, {"model": {"provider": "deepseek"},
                                           "engines": {"api": {"model": "cheap-model"}}}):
            cfg = eapi._cfg()
        self.assertEqual(cfg["model"], "cheap-model")     # 引擎级覆盖优先


class TestPurposeRouting(unittest.TestCase):
    """按用途路由：engineFor.<用途> 优先，留空回退主引擎（不配则行为与解耦前一致）。"""

    def test_falls_back_to_main_engine(self):
        with mock.patch.dict(config._CFG, {"engineFor": {}}, clear=False):
            with mock.patch.object(config, "ENGINE", "main"):
                self.assertEqual(config.engine_for("prompt"), "main")
                self.assertEqual(config.engine_for("execute"), "main")
                self.assertEqual(config.engine_for(), "main")      # 不传用途 = 主引擎

    def test_purpose_overrides_main_engine(self):
        with mock.patch.dict(config._CFG, {"engineFor": {"prompt": "api", "execute": "dsh"}}, clear=False):
            with mock.patch.object(config, "ENGINE", "main"):
                self.assertEqual(config.engine_for("prompt"), "api")
                self.assertEqual(config.engine_for("execute"), "dsh")
                self.assertEqual(config.engine_for("未约定用途"), "main")

    def test_runner_routes_by_purpose(self):
        """真实路径：runner 的两个入口按 purpose 选到对应引擎。"""
        calls = []

        def make(name):
            class _E(ebase.Engine):
                pass
            _E.name = name

            def run(self, prompt, *, timeout=600, act="", cwd=None, on_progress=None):
                calls.append(name)
                return ebase.RunResult(text="ok")

            _E.run = run
            return _E

        with mock.patch("opc_web.engines.registry._ENGINES", {"pa": make("pa"), "pb": make("pb")}):
            with mock.patch.dict(config._CFG, {"engineFor": {"prompt": "pa", "execute": "pb"}}, clear=False):
                runner.run_headless_sync("拆解用", timeout=1, purpose="prompt")
                runner.run_headless_task("执行用", timeout=1, act="T-9-S1", purpose="execute")
        self.assertEqual(calls, ["pa", "pb"])


if __name__ == "__main__":
    unittest.main()
