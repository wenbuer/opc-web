# -*- coding: utf-8 -*-
"""技能来源：dsh 用户级 / agents 平台 / npm 插件包三个根（同名去重）。

技能是**项目资产**（执行时拼进 prompt，两套引擎共用同一份），不是某个引擎的能力：
扫描逻辑在 opc_web.skills，与当前引擎无关；引擎只在 capabilities.skills 里声明
「能不能直接执行技能里那些需要工具/脚本的步骤」。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import engines, skills  # noqa: E402


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
            return skills.sources()

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

    def test_describe_reads_frontmatter(self):
        """技能说明从 SKILL.md 的 front-matter 摘出（技能页显示一行说明）。"""
        with mock.patch.object(Path, "home", classmethod(lambda cls: self._tmp)):
            got = {p.name: p for p in skills.sources()}
        self.assertIn("code-review", got)
        self.assertIn("测试用技能 code-review", skills.describe(got["code-review"] / "SKILL.md"))

    def test_skills_are_engine_independent(self):
        """技能来源与当前引擎无关；引擎只用 capabilities.skills 声明执行能力。

        dsh 自带工具沙箱，能直接跑技能里那些需要命令/读写的步骤；直连 API 引擎只有
        4 个基础工具，所以声明 False —— 但技能正文照样进 prompt，两套引擎共用一份。"""
        with mock.patch.object(Path, "home", classmethod(lambda cls: self._tmp)):
            self.assertTrue(skills.sources())                  # 有源就列，不因引擎而变
        self.assertTrue(engines.get_engine("dsh").capabilities()["skills"])
        self.assertFalse(engines.get_engine("api").capabilities()["skills"])


if __name__ == "__main__":
    unittest.main()
