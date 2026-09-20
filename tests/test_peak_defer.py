# -*- coding: utf-8 -*-
"""峰谷计价与峰时延后：时段判定、开关、谷时放行。

背景：官方 pricing 页口径 —— 峰时 = 工作日 UTC 01:00-04:00 与 06:00-10:00
（北京时间 09:00-12:00 / 14:00-18:00），其余全时段谷时，**谷时三档单价一律减半**。
"""

import datetime
import shutil
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import chain, config, runner, scheduler, store  # noqa: E402

UTC = datetime.timezone.utc


def utc(y, m, d, h, mi=0):
    return datetime.datetime(y, m, d, h, mi, tzinfo=UTC)


class TestPeakWindow(unittest.TestCase):
    def test_peak_hours(self):
        # 2026-09-15 是星期二
        self.assertTrue(config.is_peak_now(utc(2026, 9, 15, 1)))
        self.assertTrue(config.is_peak_now(utc(2026, 9, 15, 3, 59)))
        self.assertTrue(config.is_peak_now(utc(2026, 9, 15, 6)))
        self.assertTrue(config.is_peak_now(utc(2026, 9, 15, 9, 59)))

    def test_off_peak_hours(self):
        for h in (0, 4, 5, 10, 12, 23):
            self.assertFalse(config.is_peak_now(utc(2026, 9, 15, h)), "UTC %d 点应为谷时" % h)

    def test_weekend_is_all_off_peak(self):
        # 2026-09-19 周六 / 09-20 周日
        for h in range(24):
            self.assertFalse(config.is_peak_now(utc(2026, 9, 19, h)))
            self.assertFalse(config.is_peak_now(utc(2026, 9, 20, h)))

    def test_next_offpeak_is_the_end_of_the_peak_segment(self):
        # 段 [1,4) 的终点是 4:00 UTC、[6,10) 是 10:00 UTC；实现按**本机时区**呈现给人看 ——
        # 国内机器上显示 12:00 / 18:00，UTC 的 CI runner 上是 04:00 / 10:00，所以期望值也按本机时区算
        for start_h, end_h in ((2, 4), (7, 10)):
            self.assertEqual(config.next_offpeak_str(utc(2026, 9, 15, start_h)),
                             utc(2026, 9, 15, end_h).astimezone().strftime("%H:%M"))

    def test_peak_defer_default_on_and_overridable(self):
        old = config._CFG
        try:
            config._CFG = {}
            self.assertTrue(config.peak_defer(), "默认应当开启：谷时价减半是白捡的")
            config._CFG = {"peakDefer": False}
            self.assertFalse(config.peak_defer())
        finally:
            config._CFG = old


class TestOffPeakRelease(unittest.TestCase):
    """谷时到点，排队的任务要被放回「待派」——否则会永远卡在排队里。"""

    def setUp(self):
        root = Path(__file__).resolve().parent.parent / (".testroot-peak-%d" % __import__("os").getpid())
        shutil.rmtree(root, ignore_errors=True)
        (root / "批阅台").mkdir(parents=True)
        self._root = root
        self._old_roots = (config.ROOT, config.KB_ROOT, config.BATCH_ROOT, config.WORKSPACE_ROOT)
        config.ROOT = root
        config.KB_ROOT = root / "知识库"
        config.BATCH_ROOT = root / "批阅台"
        config.WORKSPACE_ROOT = root / "工作区"
        self._old_peak = config.is_peak_now
        self._old_state = dict(scheduler.SCHED_STATE)
        self._old_exec = chain.execute
        chain.execute = lambda *a, **k: None          # 别真起执行链
        scheduler.SCHED_STATE.update({"busy": False, "paused": False})
        self._no = store.add_task("峰时排队用例", "R1 判断")

    def tearDown(self):
        config.ROOT, config.KB_ROOT, config.BATCH_ROOT, config.WORKSPACE_ROOT = self._old_roots
        config.is_peak_now = self._old_peak
        chain.execute = self._old_exec
        scheduler.SCHED_STATE.clear()
        scheduler.SCHED_STATE.update(self._old_state)
        shutil.rmtree(self._root, ignore_errors=True)

    def _status(self):
        return [t["status"] for t in store.tasks() if t["no"] == self._no][0]

    def test_queued_task_is_released_when_off_peak(self):
        store.set_task(self._no, "排队", "峰时排队：已拆解 3 项，12:00 后自动开跑")
        config.is_peak_now = lambda *a, **k: False
        scheduler.scan_once()
        self.assertEqual(self._status(), "待派", "谷时到点必须放行，否则永远卡在排队")

    def test_queued_task_stays_queued_during_peak(self):
        store.set_task(self._no, "排队", "峰时排队")
        config.is_peak_now = lambda *a, **k: True
        scheduler.scan_once()
        self.assertEqual(self._status(), "排队", "峰时不许放行（否则等于白等）")


class TestForceSkipsPeakQueue(unittest.TestCase):
    """「立即执行」必须真的跳过峰时排队 —— 否则用户点了没反应，等于功能不存在。

    这是 chain.execute 里那条分支的直接验证：把拆解与执行都换成桩，
    只看「两个子任务 + 峰时」时，force 有没有把结果从「排队」掰回「开跑」。"""

    def setUp(self):
        import os
        root = Path(__file__).resolve().parent.parent / (".testroot-force-%d" % os.getpid())
        shutil.rmtree(root, ignore_errors=True)
        (root / "批阅台").mkdir(parents=True)
        (root / "工作区").mkdir(parents=True, exist_ok=True)
        self._root = root
        self._old_roots = (config.ROOT, config.KB_ROOT, config.BATCH_ROOT, config.WORKSPACE_ROOT)
        config.ROOT = root
        config.KB_ROOT = root / "知识库"
        config.BATCH_ROOT = root / "批阅台"
        config.WORKSPACE_ROOT = root / "工作区"
        self._old = (config.is_peak_now, config.peak_defer, config.PEAK_DEFER_MIN_SUBS)
        config.is_peak_now = lambda *a, **k: True          # 强行处在峰时
        config.peak_defer = lambda: True
        config.PEAK_DEFER_MIN_SUBS = 2
        self._old_state = dict(scheduler.SCHED_STATE)
        # _STOPPED 是 chain 的模块级集合，跨用例会残留（一个用例 mark_stopped 过，
        # 后面所有用例的 _alive 就都是 False）—— 必须存还原
        self._old_stopped = set(chain._STOPPED)
        chain._STOPPED.clear()
        self._old_decompose = chain.decompose
        self._old_exec = chain.execute          # 兜底：任何用例把 execute 换成桩都要还原
        self._old_run = runner.run_headless_task
        chain.decompose = lambda *a, **k: [
            {"role": "R3", "sub": "第一步", "expect": "产物"},
            {"role": "R4", "sub": "第二步", "expect": "产物"},
        ]
        runner.run_headless_task = lambda *a, **k: ("", None)   # 桩：不真跑 headless
        self._no = store.add_task("峰时排队与立即执行用例", "R1 判断")

    def tearDown(self):
        config.ROOT, config.KB_ROOT, config.BATCH_ROOT, config.WORKSPACE_ROOT = self._old_roots
        config.is_peak_now, config.peak_defer, config.PEAK_DEFER_MIN_SUBS = self._old
        chain._STOPPED.clear()
        chain._STOPPED.update(self._old_stopped)
        chain.decompose = self._old_decompose
        chain.execute = self._old_exec
        runner.run_headless_task = self._old_run
        scheduler.SCHED_STATE.clear()
        scheduler.SCHED_STATE.update(self._old_state)
        shutil.rmtree(self._root, ignore_errors=True)

    def _status(self):
        return store.get_task(self._no)["status"]

    def test_two_subtasks_at_peak_are_queued(self):
        chain.execute(self._no, "峰时排队与立即执行用例")
        self.assertEqual(self._status(), "排队", "峰时 + 2 个子任务 = 长跑，应当排队")

    def test_force_skips_the_queue_and_runs(self):
        store.set_task_force(self._no, True)
        chain.execute(self._no, "峰时排队与立即执行用例")
        self.assertNotEqual(self._status(), "排队", "点了「立即执行」就不能再排队")
        self.assertFalse(store.get_task(self._no)["force"], "豁免是一次性的，开跑后要清掉")

    def test_queued_task_still_shows_its_subtasks(self):
        """峰时排队的任务也必须落子任务行 —— 用户就是在「子任务看板 · 待派」上排序的，
        队列一堆积，最需要排序的那批恰恰是最不该隐身的那批。"""
        chain.execute(self._no, "峰时排队与立即执行用例")
        self.assertEqual(self._status(), "排队")
        subs = store.subtasks(self._no)
        self.assertEqual(len(subs), 2, "排队中也要有子任务行")
        self.assertTrue(all(s["st"] == "待派" for s in subs))

    def test_subtask_priority_survives_redecomposition(self):
        """重拆一次编号不变（T-00x-S1/S2…），调好的优先级必须按编号继承下来。"""
        rows = [{"role": "R3", "sub": "a", "expect": ""}, {"role": "R4", "sub": "b", "expect": ""}]
        store.replace_subtasks(self._no, rows)
        store.set_subtask_priority(self._no + "-S2", 2)
        store.replace_subtasks(self._no, [{"role": "R3", "sub": "a2", "expect": ""},
                                          {"role": "R4", "sub": "b2", "expect": ""}])
        self.assertEqual(store.subtasks(self._no)[1]["priority"], 2, "重拆不该把调好的优先级冲掉")

    def test_higher_priority_subtask_runs_first(self):
        """同一任务内按优先级定先后；同级的保持拆解原序。"""
        chain.execute(self._no, "峰时排队与立即执行用例")          # 先排队，把子任务行建出来
        self.assertEqual(self._status(), "排队")
        store.set_subtask_priority(self._no + "-S2", 2)           # 把第二个提到「高」
        order = []

        def fake_run(prompt, timeout=600, act="", purpose="", max_steps=None):
            order.append(act)
            return "", None
        runner.run_headless_task = fake_run
        old_peak, old_defer = config.is_peak_now, config.peak_defer
        config.is_peak_now, config.peak_defer = (lambda *a, **k: False), (lambda: True)
        try:
            chain.execute(self._no, "峰时排队与立即执行用例")       # 谷时放行 → 复用已拆好的子任务
        finally:
            config.is_peak_now, config.peak_defer = old_peak, old_defer
        # 收尾的 R1 提炼（简报 / 沉淀）也走 run_headless_task，但 act 为空 —— 只看子任务那几个
        self.assertEqual([a for a in order if a], [self._no + "-S2", self._no + "-S1"],
                         "高优先级的子任务要先跑（同级才按拆解原序）")

    def test_deleted_during_decompose_leaves_no_orphan_subtasks(self):
        """拆解期间任务被删 → 不许再写子任务行。

        删任务清的是「删除那一刻」的子任务行；执行链如果在拆解之后才走到 replace_subtasks，
        那一 INSERT 就是孤儿行 —— 任务没了、子任务还挂在看板「待派」上（T-033 自检漏下的就是它）。"""
        store.delete_task(self._no)
        chain.execute(self._no, "峰时排队与立即执行用例")
        self.assertEqual(store.subtasks(self._no), [], "任务已删，不该留下子任务行")

    def test_stopped_task_also_blocks_the_write(self):
        """同一个闸也管「被终止」的情况（mark_stopped），不只是「已删除」。"""
        chain.mark_stopped(self._no)
        chain.execute(self._no, "峰时排队与立即执行用例")
        self.assertEqual(store.subtasks(self._no), [])

    def test_second_entry_does_not_decompose_again(self):
        """二次进入链路（排队放行 / 立即执行 / 重试）**不重拆** —— 拆解在下达那一刻就做完了。

        用户点「立即执行」看到的第一件事不该是「R1 拆解中…」；而且重拆会把看板上那份
        （已经排好优先级的）列表换成另一份。"""
        calls = []

        def counting_decompose(*a, **k):
            calls.append(1)
            return [{"role": "R3", "sub": "第一步", "expect": "产物"},
                    {"role": "R4", "sub": "第二步", "expect": "产物"}]
        chain.decompose = counting_decompose
        chain.execute(self._no, "峰时排队与立即执行用例")          # 第一次：下达时实时拆
        self.assertEqual(len(calls), 1)
        before = [s["no"] for s in store.subtasks(self._no)]
        store.set_subtask_priority(before[1], 2)
        old_peak = config.is_peak_now
        config.is_peak_now = lambda *a, **k: False
        try:
            chain.execute(self._no, "峰时排队与立即执行用例")      # 第二次：谷时放行
        finally:
            config.is_peak_now = old_peak
        self.assertEqual(len(calls), 1, "已有待派子任务，不该再拆一遍")
        self.assertEqual([s["no"] for s in store.subtasks(self._no)], before,
                         "沿用时编号不变（不重排、不重建，优先级与执行记录都留着）")
    def test_priority_orders_the_pending_queue(self):
        """峰时堆积时按优先级挑下一个：高 → 普通 → 低，同级按下达先后。"""
        low = store.add_task("低", "R1 判断", 0)
        high = store.add_task("高", "R1 判断", 2)
        store.set_task(self._no, "待派")
        store.set_task(low, "待派")
        store.set_task(high, "待派")
        picked = []
        old_exec = chain.execute
        chain.execute = lambda no, *a, **k: picked.append(no)
        try:
            scheduler.scan_once()
            # scan_once 是起线程执行的，断言前等一下（最多 1 秒）
            for _ in range(50):
                if picked:
                    break
                time.sleep(0.02)
        finally:
            chain.execute = old_exec
        self.assertEqual(picked, [high], "应当先挑优先级最高的那个")


if __name__ == "__main__":
    unittest.main()
