# -*- coding: utf-8 -*-
"""技能来源：dsh 用户级 / agents 平台 / npm 插件包三个根（同名去重），且由引擎自报。

技能是**引擎的能力**，不是控制台的：扫描逻辑归 engines/dsh.py，api 引擎没有技能体系。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import engines  # noqa: E402
from opc_web.engines import dsh as edsh  # noqa: E402


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
            return edsh.skill_dirs()

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

    def test_engine_reports_its_own_skills(self):
        """引擎自报技能：dsh 给带说明的清单，api 引擎明确为空（技能页据此显示）。"""
        with mock.patch.object(Path, "home", classmethod(lambda cls: self._tmp)):
            dsh_skills = edsh.DshEngine().skills()
            api_skills = engines.get_engine("api").skills()
        self.assertEqual(api_skills, [])
        got = {s["name"]: s for s in dsh_skills}
        self.assertIn("code-review", got)
        self.assertTrue(got["code-review"]["desc"])          # 说明从 SKILL.md 的 front-matter 摘出
        self.assertTrue(got["code-review"]["path"])


if __name__ == "__main__":
    unittest.main()
