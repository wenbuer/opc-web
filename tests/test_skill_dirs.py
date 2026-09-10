# -*- coding: utf-8 -*-
"""技能目录扫描：dsh 用户级 / agents 平台 / npm 插件包三个根，同名去重。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import server  # noqa: E402


def _mk_skill(root: Path, name: str):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: 测试用技能 %s\n---\n\n正文\n" % (name, name),
        encoding="utf-8")


class TestSkillDirs(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="skilldirs-"))
        self._old = os.environ.get("DSH_HOME")
        os.environ["DSH_HOME"] = str(self._tmp / ".dsh")
        _mk_skill(self._tmp / ".dsh" / "skills", "code-review")
        _mk_skill(self._tmp / ".agents" / "skills", "python-src-project")
        _mk_skill(self._tmp / ".agents" / "skills", "code-review")     # 与 .dsh 同名
        _mk_skill(self._tmp / ".dsh" / "profiles" / "web" / "node_modules" / "pkg" / "skills", "ponytail")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("DSH_HOME", None)
        else:
            os.environ["DSH_HOME"] = self._old
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _dirs(self):
        with mock.patch.object(Path, "home", classmethod(lambda cls: self._tmp)):
            return server.Handler._dsh_skill_dirs(None)

    def test_agents_root_scanned(self):
        names = [p.name for p in self._dirs()]
        self.assertIn("python-src-project", names)
        self.assertIn("ponytail", names)

    def test_dsh_wins_on_name_clash(self):
        got = {p.name: p for p in self._dirs()}
        self.assertIn("code-review", got)
        self.assertEqual(got["code-review"].parents[1], self._tmp / ".dsh")

    def test_dedup_keeps_single_entry(self):
        names = [p.name for p in self._dirs()]
        self.assertEqual(names.count("code-review"), 1)


if __name__ == "__main__":
    unittest.main()
