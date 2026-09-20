# -*- coding: utf-8 -*-
"""Token 三档单价与成本：tokensIn 含缓存读取，成本必须拆开按各自单价算。

背景：meta 里的 tokensIn = 新输入 + 缓存读取。缓存命中单价通常只有输入的 1/10，
拿合计一律按输入价计费会把成本高估近十倍（T-028-S2 那次 1.03 亿输入里 1.028 亿是缓存）。
"""
import datetime
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from opc_web import config, scheduler  # noqa: E402

_ENVS = ("OPC_TOKEN_PRICE_IN", "OPC_TOKEN_PRICE_CACHE", "OPC_TOKEN_PRICE_OUT")


class TestTokenPrices(unittest.TestCase):
    def setUp(self):
        self._old_cfg = config._CFG
        self._env = {k: os.environ.pop(k, None) for k in _ENVS}

    def tearDown(self):
        config._CFG = self._old_cfg
        for k, v in self._env.items():
            if v is not None:
                os.environ[k] = v

    def test_cache_price_defaults_to_input_price(self):
        config._CFG = {}
        p = config.token_prices()
        self.assertEqual(p["in"], 1.0)
        self.assertEqual(p["out"], 2.0)
        self.assertEqual(p["cache"], p["in"], "缓存价留空 = 按输入价，宁可高估也不替用户猜折扣")

    def test_explicit_three_tier(self):
        config._CFG = {"priceIn": 2.0, "priceCache": 0.2, "priceOut": 8.0}
        p = config.token_prices()
        self.assertEqual((p["in"], p["cache"], p["out"]), (2.0, 0.2, 8.0))

    def test_cost_splits_cache_out_of_input(self):
        config._CFG = {"priceIn": 1.0, "priceCache": 0.1, "priceOut": 2.0}
        # 1,000,000 输入 = 100,000 新输入 + 900,000 缓存命中；输出 100,000
        got = config.token_cost(100000, 900000, 100000)
        self.assertAlmostEqual(got, 0.1 * 1.0 + 0.9 * 0.1 + 0.1 * 2.0, places=6)   # 0.39 元
        # 不拆缓存的错算法（合计按输入价 + 输出）= 1.2 元，高估三倍
        self.assertLess(got, 0.5)

    def test_negative_usage_clamped(self):
        config._CFG = {}
        self.assertGreaterEqual(config.token_cost(-5, -5, -5), 0.0)

    def test_rejects_bad_price_before_writing(self):
        with self.assertRaises(ValueError):
            config.save_prices({"priceIn": "abc"})
        with self.assertRaises(ValueError):
            config.save_prices({"priceOut": -1})


class TestHomeStatsCost(unittest.TestCase):
    """首页成本聚合：按天分桶时缓存也要跟着走，否则「今日成本」会把缓存当新输入计费。"""

    def setUp(self):
        root = Path(__file__).resolve().parent.parent / (".testroot-cost-%d" % os.getpid())
        shutil.rmtree(root, ignore_errors=True)
        (root / "工作区" / "内容与运营").mkdir(parents=True)
        (root / "批阅台").mkdir(parents=True, exist_ok=True)
        self._root = root
        self._old = (config.ROOT, config.KB_ROOT, config.BATCH_ROOT,
                     config.WORKSPACE_ROOT, config._CFG)
        config.ROOT = root
        config.KB_ROOT = root / "知识库"
        config.BATCH_ROOT = root / "批阅台"
        config.WORKSPACE_ROOT = root / "工作区"
        config._CFG = {"priceIn": 1.0, "priceCache": 0.1, "priceOut": 2.0}

    def tearDown(self):
        (config.ROOT, config.KB_ROOT, config.BATCH_ROOT,
         config.WORKSPACE_ROOT, config._CFG) = self._old
        shutil.rmtree(self._root, ignore_errors=True)

    def test_home_stats_splits_cache_and_costs_three_tiers(self):
        today = datetime.date.today().isoformat()
        (self._root / "工作区" / "内容与运营" / "T-001-S1.meta.json").write_text(json.dumps({
            "subNo": "T-001-S1", "taskNo": "T-001", "role": "R5", "createdAt": today,
            "tokensIn": 1000000, "tokensOut": 100000, "tokensCacheRead": 900000,
        }, ensure_ascii=False), encoding="utf-8")
        t = scheduler.home_stats()["tokens"]
        self.assertEqual(t["todayCache"], 900000)
        self.assertAlmostEqual(t["costToday"], 0.39, places=4)
        self.assertAlmostEqual(t["costTotal"], 0.39, places=4)
        self.assertEqual(t["totalIn"], 1000000)
        self.assertEqual(t["prices"]["cache"], 0.1)


if __name__ == "__main__":
    unittest.main()
