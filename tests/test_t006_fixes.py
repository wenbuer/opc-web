# -*- coding: utf-8 -*-
"""T-006 事故修复回归（纯标准库 unittest，不依赖真实项目/模型）：
决策上下文注入 / headless 回报有效性校验 / 会话用量不拿旧会话冒充。
运行：python -m unittest tests.test_t006_fixes -v  （在 opc-web/ 下）。
"""
import json
import os
import shutil
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import chain, config, runner, scheduler  # noqa: E402
from opc_web.engines import dsh as edsh  # noqa: E402


PIYUETAI = """## 工作内容

## 决策裁决

### 待决 6｜任务 T-004
- **任务**：设计整个APP
- **进展**：2/2 子任务完成
- **决策建议**：## 决策点
  三 tab 的 MVP 边界怎么界定？
  ## 建议
  选 A：首页闭环 + 训练完整，成长/我的轻量，P1 留 v1.5+。
- **R0 批阅**：待填
- **汇总文件**：x

### 待决 5｜任务 T-003
- **任务**：别的条目
"""


class TestDecisionContext(unittest.TestCase):
    """decision_context：任务文本里的「待决 #N」→ 批阅台对应条目的决策建议全文。"""

    def setUp(self):
        root = Path(__file__).resolve().parent.parent / (".testroot-ctx-%d" % id(self))
        shutil.rmtree(root, ignore_errors=True)
        (root / "批阅台").mkdir(parents=True)
        self._old_root = config.ROOT
        self._tmp_root = root                      # 直接保存引用：tearDown 不经 config.ROOT
        config.ROOT = root
        (root / "批阅台" / "批阅台.md").write_text(PIYUETAI, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self._tmp_root, ignore_errors=True)   # 先删测试目录
        config.ROOT = self._old_root                        # 再恢复真实 ROOT——
        # （事故教训：原写法先恢复 ROOT 再 rmtree(config.ROOT)，删的是真实 keeptalk！）

    def test_extracts_advice_for_referenced_item(self):
        ctx = scheduler.decision_context("执行 R0 决策（批阅台 待决 #6）：先实现A吧")
        self.assertIn("三 tab 的 MVP 边界怎么界定", ctx)
        self.assertIn("选 A", ctx)
        self.assertNotIn("别的条目", ctx)              # 只取被引用条目，不串台

    def test_no_reference_returns_empty(self):
        self.assertEqual(scheduler.decision_context("随便一个没有引用的任务"), "")

    def test_missing_item_returns_empty(self):
        self.assertEqual(scheduler.decision_context("执行 R0 决策（批阅台 待决 #99）：xx"), "")

    def test_chain_decision_block_wraps_context(self):
        blk = chain._decision_block("执行 R0 决策（批阅台 待决 #6）：先实现A吧")
        self.assertIn("决策上下文", blk)
        self.assertIn("选 A", blk)
        self.assertEqual(chain._decision_block("无引用任务"), "")


class TestMeaningfulReply(unittest.TestCase):
    """_meaningful_reply：乱码 / 过短 → 无效；正常回报 → 原样。"""

    def test_mojibake_rejected(self):
        self.assertEqual(chain._meaningful_reply("\ufffd" * 30), "")

    def test_too_short_rejected(self):
        self.assertEqual(chain._meaningful_reply("这个任务太大了"), "")

    def test_normal_reply_passes(self):
        ok = "## 结论\n已完成首页与训练 tab 的内容接线，成长/我的按方案 A 落轻量版，详见产出文件。" * 2
        self.assertEqual(chain._meaningful_reply(ok), ok)

    def test_slight_corruption_tolerated(self):
        body = "正常回报正文。" * 30 + "\ufffd"            # 长文里偶发 1 个替换符（<5%）不应误杀
        self.assertEqual(chain._meaningful_reply(body), body)


class TestDshCommand(unittest.TestCase):
    """_dsh_command：优先 node 直跑 bin.js（绕过 dsh.cmd shim 的 8191 字符 cmd.exe 限制）。"""

    def test_prefers_node_with_bin_js(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "node_modules" / "@deepseek-ai" / "dsh" / "lib"
            pkg.mkdir(parents=True)
            js = pkg / "bin.js"
            js.write_text("//stub", encoding="utf-8")
            with mock.patch("opc_web.engines.dsh.shutil.which",
                            side_effect=lambda n: str(Path(td) / (n + ".cmd")) if n in ("dsh", "node") else None):
                cmd = edsh._dsh_command()
            self.assertEqual(cmd[0], str(Path(td) / "node.cmd"))   # node 可执行
            self.assertEqual(cmd[1], str(js))                      # bin.js
            self.assertEqual(cmd[2:], [])

    def test_falls_back_to_dsh(self):
        from unittest import mock
        with mock.patch("opc_web.engines.dsh.shutil.which", return_value=None):
            self.assertEqual(edsh._dsh_command(), ["dsh"])


class TestGitSnapshot(unittest.TestCase):
    """_git_snapshot：非仓库静默；有变更才 commit；无变更不空提交。"""

    def _run_with(self, root_exists, status_out):
        import tempfile
        from unittest import mock
        calls = []
        def fake_run(args, capture_output=True, timeout=60):
            calls.append(args)
            r = mock.MagicMock()
            r.returncode = 0
            r.stdout = status_out if "status" in args else b""
            return r
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            if root_exists:
                (root / ".git").mkdir()
            with mock.patch("opc_web.config.ROOT", root), \
                 mock.patch("opc_web.scheduler.subprocess.run", side_effect=fake_run):
                scheduler._git_snapshot("测试")
        return calls

    def test_non_repo_silent(self):
        self.assertEqual(self._run_with(root_exists=False, status_out=b""), [])

    def test_commits_when_changes(self):
        calls = self._run_with(root_exists=True, status_out=b" M x.md")
        self.assertTrue(any("commit" in c for c in calls))

    def test_no_empty_commit(self):
        calls = self._run_with(root_exists=True, status_out=b"")
        self.assertFalse(any("commit" in c for c in calls))


class TestSessionUsageNoBorrow(unittest.TestCase):
    """read_session_usage：since 之后没有新会话 → None，不拿旧会话的用量冒充。"""

    def test_old_session_not_borrowed(self):
        import zstandard as zstd
        home = Path(__file__).resolve().parent.parent / (".testroot-dsh-%d" % id(self))
        shutil.rmtree(home, ignore_errors=True)
        sd = home / "sessions" / "keeptalk" / "session-old"
        sd.mkdir(parents=True)
        line = json.dumps({"type": "assistant/message",
                           "data": {"usage": {"inputTokens": 12632, "outputTokens": 1957,
                                              "cacheReadTokens": 0, "reasoningTokens": 0}}})
        zf = sd / "session.jsonl.zstd"
        zf.write_bytes(zstd.ZstdCompressor().compress((line + "\n").encode("utf-8")))
        past = time.time() - 3600
        os.utime(zf, (past, past))                        # 旧会话：mtime 早于 since
        old = os.environ.get("DSH_HOME")
        os.environ["DSH_HOME"] = str(home)
        try:
            self.assertIsNone(edsh.read_session_usage(since=time.time()))
        finally:
            if old is None:
                os.environ.pop("DSH_HOME", None)
            else:
                os.environ["DSH_HOME"] = old
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
