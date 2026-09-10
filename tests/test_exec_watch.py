# -*- coding: utf-8 -*-
"""执行事件追踪：_exec_beat 状态值 / events() 透出 / _watch_session 会话增量解析。

背景：headless 只在期末输出一次 final 文本，stdout 全程静默——900 秒「无输出强杀」
曾把正常干活 15+ 分钟的 R3/R4 误判阻塞（T-006 两次）。修复 = 追踪 dsh 会话事件日志
（~/.dsh/sessions/<cwd>/session-*.jsonl.zstd）作为活动心跳，借鉴 dsh-better-sidebar
的 lastActivity 折叠（只取 tool/call 与 assistant/message）。"""
import json
import os
import time
import types
import os
import sys
import tempfile
import unittest
import shutil
from pathlib import Path

import zstandard as zstd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import chain, config, runner  # noqa: E402


def _zst_write(path: Path, events: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events)
    path.write_bytes(zstd.ZstdCompressor().compress(lines.encode("utf-8")))


class TestExecState(unittest.TestCase):
    def tearDown(self):
        with runner._EXEC_LOCK:
            runner._EXEC_STATE.clear()

    def test_exec_beat_updates_state_and_emits(self):
        t0 = time.monotonic() - 100
        runner._exec_beat("T-006-S1", 3, "pwsh 修改 keeptalk-server.py", "接线中", t0)
        st = runner.exec_state()["T-006-S1"]
        self.assertEqual(st["tools"], 3)
        self.assertIn("pwsh", st["lastTool"])
        self.assertEqual(st["lastText"], "接线中")
        evs = runner.events(0)["events"]
        self.assertEqual(evs[-1]["type"], "exec/progress")
        self.assertEqual(evs[-1]["data"]["sub"], "T-006-S1")
        self.assertEqual(evs[-1]["data"]["tools"], 3)

    def test_events_state_carries_exec(self):
        runner._exec_beat("T-001-S1", 1, "read", "", time.monotonic())
        state = runner.events(0)["state"]
        self.assertIn("exec", state)
        self.assertIn("T-001-S1", state["exec"])


class TestWatchSession(unittest.TestCase):
    def setUp(self):
        home = Path(__file__).resolve().parent.parent / (".testroot-watch-%d" % id(self))
        shutil.rmtree(home, ignore_errors=True)
        self._home = home
        root = home / "proj"
        root.mkdir(parents=True)
        self._old_root = config.ROOT
        config.ROOT = root
        self._act = "T-006-S1"
        with runner._EXEC_LOCK:
            runner._EXEC_STATE.pop(self._act, None)
        self._old_home_env = os.environ.get("DSH_HOME")

    def tearDown(self):
        config.ROOT = self._old_root
        if self._old_home_env is None:
            os.environ.pop("DSH_HOME", None)
        else:
            os.environ["DSH_HOME"] = self._old_home_env
        shutil.rmtree(self._home, ignore_errors=True)
        with runner._EXEC_LOCK:
            runner._EXEC_STATE.pop(self._act, None)

    def test_watch_session_folds_tools_and_beats(self):
        os.environ["DSH_HOME"] = str(self._home)
        sess_dir = runner._dsh_sessions_dir() / "keeptalk" / "session-w1"
        cwd = str(config.ROOT)
        task = "执行子任务：梳理现有项目内容并迁移代码"
        _zst_write(sess_dir / "session.jsonl.zstd", [
            {"type": "session", "cwd": cwd},
            {"type": "user/message", "data": {"message": {"content": [
                {"type": "text", "text": task}]}}},
            {"type": "tool/call", "data": {"name": "pwsh", "arguments": "git status"}},
            {"type": "assistant/message", "data": {"message": {"content": [
                {"type": "text", "text": "正在执行子任务"}]}}},
        ])
        # poll 序列：第一轮 None（进入解析、找到会话并折叠），第二轮 0（退出）
        p = types.SimpleNamespace(poll=lambda: [None, 0].pop(0) if getattr(p, "_n", 0) else None)
        calls = {"n": 0}
        class _P:
            def poll(self_inner):
                calls["n"] += 1
                return None if calls["n"] == 1 else 0
        runner._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                              set(), task)
        st = runner.exec_state()[self._act]
        self.assertEqual(st["tools"], 1)
        self.assertIn("pwsh", st["lastTool"])
        self.assertIn("git status", st["lastTool"])
        self.assertEqual(st["lastText"], "正在执行子任务")
        self.assertTrue(st["session"])
        evs = runner.events(0)["events"]
        self.assertTrue(any(e["type"] == "exec/progress" and e["data"]["sub"] == self._act
                            for e in evs))

    def test_watch_skips_session_present_before_spawn(self):
        """pre 快照里的会话不是本次任务的，不得认领（否则会显示别的会话的文本）。"""
        os.environ["DSH_HOME"] = str(self._home)
        sess_dir = runner._dsh_sessions_dir() / "keeptalk" / "session-old"
        task = "执行子任务：梳理现有项目内容并迁移代码"
        _zst_write(sess_dir / "session.jsonl.zstd", [
            {"type": "session", "cwd": str(config.ROOT)},
            {"type": "user/message", "data": {"message": {"content": [
                {"type": "text", "text": task}]}}},
            {"type": "assistant/message", "data": {"message": {"content": [
                {"type": "text", "text": "别的会话的文本"}]}}},
        ])

        class _P:
            def poll(self_inner):
                return 0
        runner._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                              {"session-old"}, task)
        self.assertNotIn(self._act, runner.exec_state())

    def test_watch_requires_prompt_match(self):
        """cwd 相同但任务文本对不上的会话不得认领（T-007-S1 认领错会话的根因）。"""
        os.environ["DSH_HOME"] = str(self._home)
        sess_dir = runner._dsh_sessions_dir() / "keeptalk" / "session-other"
        _zst_write(sess_dir / "session.jsonl.zstd", [
            {"type": "session", "cwd": str(config.ROOT)},
            {"type": "user/message", "data": {"message": {"content": [
                {"type": "text", "text": "你是别的角色的会话，和本次任务无关"}]}}},
            {"type": "assistant/message", "data": {"message": {"content": [
                {"type": "text", "text": "| T-001 | 别的表格 | R3 | 产出 | 待派 |"}]}}},
        ])

        class _P:
            def poll(self_inner):
                return 0
        runner._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                              set(), "执行子任务：梳理现有项目内容并迁移代码")
        self.assertNotIn(self._act, runner.exec_state())

    def test_watch_session_skips_foreign_cwd(self):
        os.environ["DSH_HOME"] = str(self._home)
        sess_dir = runner._dsh_sessions_dir() / "other-proj" / "session-x1"
        _zst_write(sess_dir / "session.jsonl.zstd", [
            {"type": "session", "cwd": "C:\\somewhere-else"},
            {"type": "tool/call", "data": {"name": "pwsh", "arguments": "rm"}},
        ])
        class _P:
            def poll(self_inner):
                return 0      # 立即结束：只应完成"找不到匹配会话"的静默退出
        runner._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30)
        self.assertNotIn(self._act, runner.exec_state())


class TestUsageFromClaimedSession(unittest.TestCase):
    """usage 抽取优先用已认领的会话：按 mtime 猜在并发下会选空/选错（T-008-S1 正常完成却无用量）。"""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="usage-"))
        self._old_home = os.environ.get("DSH_HOME")
        os.environ["DSH_HOME"] = str(self._tmp)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("DSH_HOME", None)
        else:
            os.environ["DSH_HOME"] = self._old_home
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _mk_session(self, name, mtime_ago=3600.0):
        d = runner._dsh_sessions_dir() / "proj" / name
        _zst_write(d / "session.jsonl.zstd", [
            {"type": "session", "cwd": "C:/x/proj"},
            {"type": "assistant/message", "data": {"usage": {
                "inputTokens": 100, "outputTokens": 20,
                "cacheReadTokens": 900, "reasoningTokens": 3}}},
        ])
        past = time.time() - mtime_ago
        os.utime(d / "session.jsonl.zstd", (past, past))
        return d

    def test_claimed_session_wins_over_since_filter(self):
        d = self._mk_session("session-old", mtime_ago=3600)
        # 按 mtime 猜：会话早于 since → 抽不到
        self.assertIsNone(runner.read_session_usage(since=time.time()))
        # 给定已认领的会话：直接取到用量
        got = runner.read_session_usage(since=time.time(), session_dir=d)
        self.assertEqual(got["inputTokens"], 100)
        self.assertEqual(got["cacheReadTokens"], 900)

    def test_none_session_falls_back_to_scan(self):
        d = self._mk_session("session-new", mtime_ago=0)
        got = runner.read_session_usage(since=time.time() - 60, session_dir=None)
        self.assertIsNotNone(got)
        self.assertEqual(got["outputTokens"], 20)


class TestPutTokens(unittest.TestCase):
    """token 记账：完成与阻塞两条路径共用；usage 为空不写字段。"""

    def test_writes_four_fields(self):
        meta = {"subNo": "T-1-S1"}
        chain._put_tokens(meta, {"inputTokens": 10, "outputTokens": 2,
                                "cacheReadTokens": 90, "reasoningTokens": 1})
        self.assertEqual(meta["tokensIn"], 100)      # 计费口径 = input + cacheRead
        self.assertEqual(meta["tokensOut"], 2)
        self.assertEqual(meta["tokensCacheRead"], 90)
        self.assertEqual(meta["tokensReasoning"], 1)

    def test_empty_usage_writes_nothing(self):
        meta = {"subNo": "T-1-S1"}
        chain._put_tokens(meta, None)
        chain._put_tokens(meta, {})
        self.assertEqual([k for k in meta if "token" in k], [])


class TestLandedEvidence(unittest.TestCase):
    """headless 无输出时的核盘：落盘了就不判阻塞（T-007-S1 实际完成却被判阻塞）。"""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="landed-"))
        self._old_root = config.ROOT
        config.ROOT = self._tmp
        (self._tmp / "项目").mkdir()

    def tearDown(self):
        config.ROOT = self._old_root
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_evidence_from_report_growth_and_project_files(self):
        body = self._tmp / "T-007-S1-report.md"
        body.write_text("骨架\n" * 2, encoding="utf-8")
        size0 = body.stat().st_size
        body.write_text("骨架\n" * 20, encoding="utf-8")          # 本轮写入
        (self._tmp / "项目" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        ev = chain._landed_evidence(body, size0, time.time() - 120)
        self.assertTrue(any("回报文件已写入" in x for x in ev))
        self.assertTrue(any("《项目/》" in x for x in ev))

    def test_no_evidence_when_nothing_landed(self):
        body = self._tmp / "T-007-S1-report.md"
        body.write_text("骨架\n", encoding="utf-8")
        old = self._tmp / "项目" / "old.py"
        old.write_text("pass\n", encoding="utf-8")
        past = time.time() - 86400
        os.utime(old, (past, past))                                 # 旧文件不算本轮落盘
        ev = chain._landed_evidence(body, body.stat().st_size, time.time() - 60)
        self.assertEqual(ev, [])

    def test_missing_report_file_does_not_raise(self):
        ev = chain._landed_evidence(self._tmp / "nope.md", 0, time.time())
        self.assertEqual(ev, [])


if __name__ == "__main__":
    unittest.main()
