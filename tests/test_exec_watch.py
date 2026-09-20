# -*- coding: utf-8 -*-
"""执行事件追踪：_exec_beat 状态值 / events() 透出 / _watch_session 会话增量解析。

背景：headless 只在期末输出一次 final 文本，stdout 全程静默——900 秒「无输出强杀」
曾把正常干活 15+ 分钟的 R3/R4 误判阻塞（T-006 两次）。修复 = 追踪 dsh 会话事件日志
（~/.dsh/sessions/<cwd>/session-*.jsonl.zstd）作为活动心跳，借鉴 dsh-better-sidebar
的 lastActivity 折叠（只取 tool/call 与 assistant/message）。"""
import json
import os
import shutil
import sys
import time
import types
import unittest
from pathlib import Path

import zstandard as zstd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _tmpdir import mk_tmp  # noqa: E402

from opc_web import chain, config, runner  # noqa: E402
from opc_web.engines import dsh as edsh  # noqa: E402


def _zst_write(path: Path, events: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events)
    path.write_bytes(zstd.ZstdCompressor().compress(lines.encode("utf-8")))


class TestExecState(unittest.TestCase):
    def tearDown(self):
        with runner._EXEC_LOCK:
            runner._EXEC_STATE.clear()
            runner._DONE_ACTS.clear()

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

    def test_late_beat_after_finished_does_not_resurrect_state(self):
        """收尾期迟到的心跳不得重建「执行中」。

        dsh 的会话监听线程比 finished 晚一步退出，它最后那次 _report 会在 finished 之后
        落到这里。放它进来，状态就再也没人清除 —— 界面永远显示在跑，而归档守卫
        （r1_archive 按 exec_state 跳过执行中的子任务）会永久挡住这个子任务，
        于是子任务状态永远停在「执行中」（T-028-S2 实测卡死）。"""
        from opc_web.engines.base import Progress
        sink = runner._progress_sink("T-028-S2")
        sink(Progress(tools=438, lastTool="todo_write", lastText="交付完成"))
        self.assertIn("T-028-S2", runner.exec_state())
        sink(Progress(finished=True))
        self.assertNotIn("T-028-S2", runner.exec_state())
        sink(Progress(tools=438, lastTool="todo_write", lastText="交付完成"))   # 迟到心跳
        self.assertNotIn("T-028-S2", runner.exec_state())

    def test_late_session_write_does_not_create_empty_shell(self):
        """迟到回调里的 session 补写不得凭空造出空壳条目。

        那条 setdefault 会建出一个 startedAt/elapsed 全空的壳，而归档守卫只看「键在不在」——
        壳照样把子任务永久挡在归档之外，等于绕过 _exec_beat 里那道闸。"""
        from opc_web.engines.base import Progress
        sink = runner._progress_sink("T-030-S1")
        sink(Progress(finished=True))
        sink(Progress(session="session-abc"))          # 只有 session、没有任何心跳字段
        self.assertNotIn("T-030-S1", runner.exec_state())

    def test_new_run_unfreezes_the_act(self):
        """同一子任务重试：新一轮的进度必须能重新建出「执行中」。"""
        from opc_web.engines.base import Progress
        runner._progress_sink("T-028-S2")(Progress(finished=True))
        self.assertNotIn("T-028-S2", runner.exec_state())
        runner._progress_sink("T-028-S2")(Progress(tools=1, lastTool="read"))
        self.assertIn("T-028-S2", runner.exec_state())


class TestWatchSession(unittest.TestCase):
    def setUp(self):
        home = Path(__file__).resolve().parent.parent / (".testroot-watch-%d" % id(self))
        shutil.rmtree(home, ignore_errors=True)
        self._home = home
        root = home / "proj"
        root.mkdir(parents=True)
        # 三目录一起隔离：runner 的完整轨迹落盘走 BATCH_ROOT，
        # 只改 ROOT 会让测试把《批阅台/运行日志/》写进真实项目
        self._old_root = (config.ROOT, config.KB_ROOT, config.BATCH_ROOT, config.WORKSPACE_ROOT)
        config.ROOT = root
        config.KB_ROOT = root / "知识库"
        config.BATCH_ROOT = root / "批阅台"
        config.WORKSPACE_ROOT = root / "工作区"
        self._act = "T-006-S1"
        with runner._EXEC_LOCK:
            runner._EXEC_STATE.pop(self._act, None)
        self._old_home_env = os.environ.get("DSH_HOME")

    def tearDown(self):
        (config.ROOT, config.KB_ROOT, config.BATCH_ROOT,
         config.WORKSPACE_ROOT) = self._old_root
        if self._old_home_env is None:
            os.environ.pop("DSH_HOME", None)
        else:
            os.environ["DSH_HOME"] = self._old_home_env
        shutil.rmtree(self._home, ignore_errors=True)
        with runner._EXEC_LOCK:
            runner._EXEC_STATE.pop(self._act, None)

    def test_pure_trace_progress_does_not_clobber_tool_count(self):
        """只带轨迹、不带心跳字段的回调不进心跳：否则界面显示「操作 0 次」（实际跑了 57 次）。"""
        from opc_web.engines.base import Progress
        sink = runner._progress_sink(self._act)
        sink(Progress(tools=7, lastTool="pwsh git status"))
        self.assertEqual(7, runner.exec_state()[self._act]["tools"])
        before = runner.events(0)["state"]["seq"]
        sink(Progress(trace={"kind": "reasoning", "text": "先看一眼现状"}))
        st = runner.exec_state()[self._act]
        self.assertEqual(7, st["tools"], "纯轨迹回调不得清零操作数")
        self.assertIn("pwsh", st["lastTool"])
        evs = [e for e in runner.events(before)["events"] if e["type"] == "exec/trace"]
        self.assertTrue(evs, "轨迹要进事件流")

    def test_watch_session_folds_tools_and_beats(self):
        os.environ["DSH_HOME"] = str(self._home)
        sess_dir = edsh._dsh_sessions_dir() / "keeptalk" / "session-w1"
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
        edsh._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                              set(), task, on_progress=runner._progress_sink(self._act))
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
        sess_dir = edsh._dsh_sessions_dir() / "keeptalk" / "session-old"
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
        edsh._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                              {"session-old"}, task, on_progress=runner._progress_sink(self._act))
        self.assertNotIn(self._act, runner.exec_state())

    def test_watch_requires_prompt_match(self):
        """cwd 相同但任务文本对不上的会话不得认领（T-007-S1 认领错会话的根因）。"""
        os.environ["DSH_HOME"] = str(self._home)
        sess_dir = edsh._dsh_sessions_dir() / "keeptalk" / "session-other"
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
        edsh._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                              set(), "执行子任务：梳理现有项目内容并迁移代码",
                              on_progress=runner._progress_sink(self._act))
        self.assertNotIn(self._act, runner.exec_state())

    def test_watch_session_skips_foreign_cwd(self):
        os.environ["DSH_HOME"] = str(self._home)
        sess_dir = edsh._dsh_sessions_dir() / "other-proj" / "session-x1"
        _zst_write(sess_dir / "session.jsonl.zstd", [
            {"type": "session", "cwd": "C:\\somewhere-else"},
            {"type": "tool/call", "data": {"name": "pwsh", "arguments": "rm"}},
        ])
        class _P:
            def poll(self_inner):
                return 0      # 立即结束：只应完成"找不到匹配会话"的静默退出
        edsh._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                              on_progress=runner._progress_sink(self._act))
        self.assertNotIn(self._act, runner.exec_state())


class TestBudgetGuard(unittest.TestCase):
    """预算护栏：dsh 没有步数开关，只能在会话事件流上自己数着拦。

    阈值来自 11 个子任务的实测分布：正常 36~136 轮 / 56~164 次工具 / 2.6M~17.3M token；
    失控样本 T-028-S2 407 轮 / 438 次工具 / 103M token（占全项目 59%）。"""

    def setUp(self):
        self._act = "T-999-S1"
        self._old_guard = dict(edsh.GUARD)
        with edsh._STATE_LOCK:
            edsh._TRIP.pop(self._act, None)
            edsh._KILLED.pop(self._act, None)
        self._home = Path(__file__).resolve().parent.parent / (".testroot-guard-%d" % id(self))
        shutil.rmtree(self._home, ignore_errors=True)
        self._old_home_env = os.environ.get("DSH_HOME")
        os.environ["DSH_HOME"] = str(self._home)

    def tearDown(self):
        edsh.GUARD.clear()
        edsh.GUARD.update(self._old_guard)
        with edsh._STATE_LOCK:
            edsh._TRIP.pop(self._act, None)
            edsh._KILLED.pop(self._act, None)
        if self._old_home_env is None:
            os.environ.pop("DSH_HOME", None)
        else:
            os.environ["DSH_HOME"] = self._old_home_env
        shutil.rmtree(self._home, ignore_errors=True)

    def _run_watch(self, events, cwd):
        """跑一轮 _watch_session（poll 第一次 None → 处理完全部事件 → 退出）。

        必须带上与 prompt_head 对得上的 user/message —— 会话认领的第三重校验就是这个，
        缺了它会话根本认领不到，事件一条也不会被处理（护栏自然也永远不触发）。"""
        d = edsh._dsh_sessions_dir() / "proj" / "session-g1"
        head = {"type": "user/message", "data": {"message": {"content": [
            {"type": "text", "text": "guard probe task"}]}}}
        _zst_write(d / "session.jsonl.zstd", [{"type": "session", "cwd": cwd}, head] + events)
        calls = {"n": 0}

        class _P:
            def poll(self_inner):
                calls["n"] += 1
                return None if calls["n"] == 1 else 0
        edsh._watch_session(self._act, _P(), time.time() - 30, time.monotonic() - 30,
                            set(), "guard probe task", on_progress=runner._progress_sink(self._act))

    def _msgs(self, n, in_tok=100):
        return [{"type": "assistant/message", "data": {
            "usage": {"inputTokens": in_tok, "cacheReadTokens": 0, "outputTokens": 1},
            "message": {"content": [{"type": "text", "text": "ok"}]}}} for _ in range(n)]

    def test_trips_on_turn_count(self):
        edsh.GUARD["maxTurns"] = 3
        self._run_watch(self._msgs(5), str(config.ROOT))
        self.assertIn("轮数", edsh._TRIP.get(self._act, ""))

    def test_trips_on_input_token_budget(self):
        edsh.GUARD["maxInputTokens"] = 250
        self._run_watch(self._msgs(5, in_tok=100), str(config.ROOT))
        self.assertIn("累计输入", edsh._TRIP.get(self._act, ""))

    def test_trips_on_tool_calls(self):
        edsh.GUARD["maxTools"] = 2
        ev = [{"type": "tool/call", "data": {"name": "pwsh", "arguments": "git status"}} for _ in range(4)]
        self._run_watch(ev, str(config.ROOT))
        self.assertIn("工具调用", edsh._TRIP.get(self._act, ""))

    def test_no_trip_within_budget(self):
        self._run_watch(self._msgs(5, in_tok=10), str(config.ROOT))
        self.assertNotIn(self._act, edsh._TRIP)

    def test_killed_is_not_reported_as_engine_error(self):
        """被中止只标 killed，**不能**写 error —— error 会被判成「引擎没跑起来」而回退重跑。"""
        old = edsh._run_prompt_dsh
        edsh._run_prompt_dsh = lambda *a, **k: ("", None, "", "预算护栏：轮数 301 超过上限 300")
        try:
            res = edsh.DshEngine().run("x")
        finally:
            edsh._run_prompt_dsh = old
        self.assertTrue(res.killed)
        self.assertEqual(res.error, "")
        self.assertFalse(runner._engine_failed(res), "中止的运行不得触发引擎回退重跑")


class TestUsageFromClaimedSession(unittest.TestCase):
    """usage 抽取优先用已认领的会话：按 mtime 猜在并发下会选空/选错（T-008-S1 正常完成却无用量）。"""

    def setUp(self):
        self._tmp = mk_tmp("usage")
        self._old_home = os.environ.get("DSH_HOME")
        os.environ["DSH_HOME"] = str(self._tmp)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("DSH_HOME", None)
        else:
            os.environ["DSH_HOME"] = self._old_home
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _mk_session(self, name, mtime_ago=3600.0):
        d = edsh._dsh_sessions_dir() / "proj" / name
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
        self.assertIsNone(edsh.read_session_usage(since=time.time()))
        # 给定已认领的会话：直接取到用量
        got = edsh.read_session_usage(since=time.time(), session_dir=d)
        self.assertEqual(got["inputTokens"], 100)
        self.assertEqual(got["cacheReadTokens"], 900)

    def test_none_session_falls_back_to_scan(self):
        d = self._mk_session("session-new", mtime_ago=0)
        got = edsh.read_session_usage(since=time.time() - 60, session_dir=None)
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


class TestSettleSub(unittest.TestCase):
    """执行结果当场落定：结算执行记录 **和** 翻转子任务状态，缺一个就出「永远执行中」。

    原先只结算执行记录，把翻状态整个留给归档器（双重所有权）：执行链明知自己跑完了
    却不说，归档器一旦被守卫挡住，子任务就永远停在「执行中」—— T-028-S2 实测如此。"""

    def _capture(self):
        calls = []

        class _S:
            @staticmethod
            def settle_execution(no, st, err=""):
                calls.append(("exec", no, st, err))

            @staticmethod
            def set_subtask(no, st):
                calls.append(("sub", no, st))

        old = chain.store
        chain.store = _S
        self.addCleanup(setattr, chain, "store", old)
        return calls

    def test_completion_settles_execution_and_flips_subtask(self):
        calls = self._capture()
        chain._settle_sub("T-028-S2", "完成")
        self.assertEqual(calls, [("exec", "T-028-S2", "完成", ""),
                                 ("sub", "T-028-S2", "完成")])

    def test_blocked_path_keeps_error_text(self):
        calls = self._capture()
        chain._settle_sub("T-028-S2", "阻塞", "headless 无输出")
        self.assertEqual(calls, [("exec", "T-028-S2", "阻塞", "headless 无输出"),
                                 ("sub", "T-028-S2", "阻塞")])


class TestLandedEvidence(unittest.TestCase):
    """headless 无输出时的核盘：落盘了就不判阻塞（T-007-S1 实际完成却被判阻塞）。"""

    def setUp(self):
        self._tmp = mk_tmp("landed")
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
