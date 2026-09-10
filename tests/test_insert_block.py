# -*- coding: utf-8 -*-
"""批阅台条目插入：不得劈坏三级标题（T-007 插入时 T-006 因为 find("## ") 误命中而消失）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import scheduler  # noqa: E402

BASE = """## 工作内容

### 工作 1｜任务 T-001
- **任务**：示例

## 决策裁决

### 待决 8｜任务 T-006
- **任务**：旧待决
- **R0 批阅**：待填

## 已批阅归档
"""


class TestInsertBlock(unittest.TestCase):
    def test_three_level_head_not_split(self):
        blk = "\n### 待决 9｜任务 T-007\n- **任务**：新待决\n"
        out = scheduler.insert_block(BASE, "## 决策裁决", blk)
        self.assertIn("### 待决 8｜任务 T-006", out)      # 旧条目标题级别不变
        self.assertNotIn("\n## 待决 8", out)             # 不得降级成二级
        self.assertIn("### 待决 9｜任务 T-007", out)
        self.assertEqual(out.count("### 待决"), 2)

    def test_no_stray_hash_line(self):
        blk = "\n### 待决 9｜任务 T-007\n- **任务**：新待决\n"
        out = scheduler.insert_block(BASE, "## 决策裁决", blk)
        self.assertNotIn("\n#\n", out)                   # 不留孤立 # 行

    def test_inserted_before_next_section(self):
        blk = "\n### 待决 9｜任务 T-007\n"
        out = scheduler.insert_block(BASE, "## 决策裁决", blk)
        self.assertLess(out.index("待决 9"), out.index("## 已批阅归档"))

    def test_work_section_moves_to_end_of_its_own_section(self):
        blk = "\n### 工作 2｜任务 T-002\n"
        out = scheduler.insert_block(BASE, "## 工作内容", blk)
        self.assertIn("### 工作 1｜任务 T-001", out)
        self.assertLess(out.index("工作 2"), out.index("## 决策裁决"))

    def test_section_missing_appends(self):
        out = scheduler.insert_block("## 工作内容\n", "## 决策裁决", "\n### 待决 1｜任务 T-1\n")
        self.assertTrue(out.rstrip().endswith("### 待决 1｜任务 T-1"))


if __name__ == "__main__":
    unittest.main()
