# -*- coding: utf-8 -*-
"""《员工手册》：唯一来源是 agents-seed/员工手册.md，代码里不留副本。

以前正文是 templates.py 里的 HANDBOOK 常量，再由 build.ps1 从代码导出到 _seed/ 做覆盖层 ——
同一份内容在 代码 / _seed / 知识库 三处各留一份，改一处忘一处就分叉。
改成读文件后，这条测试守住「它是文件驱动的、且文件缺了就老实返回空（不拿旧副本顶替）」。
"""
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, templates  # noqa: E402


class TestHandbookSource(unittest.TestCase):
    def setUp(self):
        self._old = config.AGENTS_SEED
        # 受限环境（沙箱/CI）下 mkdtemp 的 0700 目录常不可再写，用普通目录
        self._dir = Path(__file__).resolve().parent.parent / (".testroot-hb-%d" % id(self))
        shutil.rmtree(self._dir, ignore_errors=True)
        self._dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        config.AGENTS_SEED = self._old
        shutil.rmtree(self._dir, ignore_errors=True)

    def test_ships_with_the_repo(self):
        t = templates.handbook_text()
        self.assertGreater(len(t), 500, "手册正文不该是空的")
        self.assertTrue(t.lstrip().startswith("# 员工手册"), t[:40])
        self.assertIn("## 1. 决策与权限", t)
        self.assertIn("不拍板", t)
        self.assertTrue(t.endswith(chr(10)), "正文以换行结尾，写进知识库时格式才稳定")

    def test_reads_the_file_not_a_hardcoded_copy(self):
        """把 AGENTS_SEED 指到临时目录，返回值必须跟着变 —— 否则说明代码里还留着副本。"""
        (self._dir / "员工手册.md").write_text("# 员工手册" + chr(10) + "临时内容" + chr(10), encoding="utf-8")
        config.AGENTS_SEED = self._dir
        self.assertEqual(templates.handbook_text().strip(),
                         "# 员工手册" + chr(10) + "临时内容")

    def test_missing_file_returns_empty_not_a_stale_copy(self):
        config.AGENTS_SEED = self._dir          # 目录是空的
        self.assertEqual(templates.handbook_text(), "")


if __name__ == "__main__":
    unittest.main()
