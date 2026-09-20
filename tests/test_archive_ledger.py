# -*- coding: utf-8 -*-
"""归档登记去重：内容交付物留在工作区，重复归档不得重复登记。

缺陷背景：归档登记的是「仍留在工作区、没有 meta 的内容交付物」，归档不会把它们移走，
于是每次扫描都重登记一遍 —— 2026-09-11 那份被写成 245 行（13 项重复 6 遍）。
"""
import datetime
import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, scheduler  # noqa: E402


class TestArchiveLedger(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent.parent / (".testarc-%d-%s" % (os.getpid(), id(self)))
        shutil.rmtree(root, ignore_errors=True)
        (root / "工作区" / "全栈开发").mkdir(parents=True)
        self._root = root
        self._old = (config.ROOT, config.KB_ROOT, config.BATCH_ROOT, config.WORKSPACE_ROOT,
                     config.AGENTS_DIR, config.LOG_FILE)
        config.ROOT = root
        config.KB_ROOT = root / "知识库"
        config.BATCH_ROOT = root / "批阅台"
        config.WORKSPACE_ROOT = root / "工作区"
        config.AGENTS_DIR = root / "agents"
        config.LOG_FILE = root / "批阅台" / "调度日志.md"

    def tearDown(self):
        (config.ROOT, config.KB_ROOT, config.BATCH_ROOT, config.WORKSPACE_ROOT,
         config.AGENTS_DIR, config.LOG_FILE) = self._old
        shutil.rmtree(self._root, ignore_errors=True)

    def _ledger_file(self):
        return config.BATCH_ROOT / ("归档登记-" + datetime.date.today().isoformat() + ".md")

    def test_repeated_archive_registers_once(self):
        f = config.WORKSPACE_ROOT / "全栈开发" / "交付物.md"
        f.write_text("内容交付物，没有 meta.json", encoding="utf-8")
        scheduler.r1_archive()
        lg = self._ledger_file()
        self.assertTrue(lg.is_file(), "首次归档应建立登记文件")
        first = lg.read_text(encoding="utf-8")
        self.assertEqual(1, first.count("- 全栈开发/交付物.md"))
        # 文件仍在工作区 → 再归档两次不得重复登记
        scheduler.r1_archive()
        scheduler.r1_archive()
        self.assertEqual(first, lg.read_text(encoding="utf-8"))

    def test_completed_task_reported_once(self):
        """任务级回填只在状态真的变化时上报：否则每次归档都把历史任务重报一遍。"""
        from opc_web import store
        no = store.add_task("测试任务", "R1 判断")
        store.replace_subtasks(no, [{"sub": "干活", "role": "全栈开发", "status": "完成"}])
        first = scheduler.r1_archive()
        self.assertIn(no + " → 任务完成", first["archived"])
        second = scheduler.r1_archive()
        self.assertNotIn(no + " → 任务完成", second["archived"])
        self.assertEqual(["完成"], [t["status"] for t in store.tasks() if t["no"] == no])

    def test_new_deliverable_appends_after_existing(self):
        d = config.WORKSPACE_ROOT / "全栈开发"
        (d / "第一份.md").write_text("x", encoding="utf-8")
        scheduler.r1_archive()
        (d / "第二份.md").write_text("y", encoding="utf-8")
        scheduler.r1_archive()
        txt = self._ledger_file().read_text(encoding="utf-8")
        self.assertEqual(1, txt.count("- 全栈开发/第一份.md"))
        self.assertEqual(1, txt.count("- 全栈开发/第二份.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
