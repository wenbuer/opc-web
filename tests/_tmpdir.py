# -*- coding: utf-8 -*-
"""用例临时目录：仓库内的普通目录，不用 tempfile。

受限环境（沙箱 / CI 容器）下 `tempfile.mkdtemp` 的 0700 目录常不可再写，
用例在建子目录时就 PermissionError（实测 api_engine / exec_watch /
skill_dirs / t006_fixes 四个套件全挂在这上面）。统一走这里，症状消失；
目录落在仓库根，.gitignore 已排除。
"""
import contextlib
import os
import shutil
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def mk_tmp(tag: str) -> Path:
    """仓库内的一次性目录，调用方负责删（或在 tearDown 里 rmtree）。"""
    d = _ROOT / (".testroot-%s-%d" % (tag, os.getpid()))
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextlib.contextmanager
def tmp_dir(tag: str):
    """with 写法：出块即删。"""
    d = mk_tmp(tag)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
