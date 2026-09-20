# -*- coding: utf-8 -*-
"""跑全部用例：python scripts/run_tests.py

tests/test_*.py 都是自带 unittest.main() 的独立脚本（互相不共享状态、可单独跑），
这里逐个起子进程跑，避免模块级的 sys.path / config 补丁互相污染。
装了 zstandard 才能跑 dsh 用量与心跳那两个套件。

在 GitHub Actions 里（GITHUB_ACTIONS=true）失败时多做两件事，都是为了「没有 token
也能定位」——CI 的原始日志要登录才下得下来：
  1. 把失败用例的尾部输出打成 ::error 注解（挂到 commit 的 checks 上，公开可读）；
  2. 写进 job summary（在 run 页面直接能看到哪几个失败）。
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
_IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def _tail(text: str, n: int = 6) -> str:
    """取尾部若干行压成一行（注解里不能有裸换行）。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return " | ".join(lines[-n:])[:900]


def _summary(rows) -> None:
    """把结果写进 job summary（本地没有这个环境变量，什么也不做）。"""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
    except Exception:
        pass


def main() -> int:
    try:
        # 控制台编不出中文时退成 ?，别让汇总行自己抛 UnicodeEncodeError
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    files = sorted(TESTS.glob("test_*.py"))
    if not files:
        print("没有找到用例（tests/test_*.py）")
        return 1
    failed = []
    tails = {}
    for f in files:
        p = subprocess.run([sys.executable, str(f)], cwd=str(ROOT),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
        print(out, end="", flush=True)
        print("%s  %s" % ("PASS" if p.returncode == 0 else "FAIL", f.name), flush=True)
        if p.returncode != 0:
            failed.append(f.name)
            tails[f.name] = _tail(out)
            if _IN_CI:
                # 注解正文里 % 要转义，否则 GitHub 解析坏掉
                msg = tails[f.name].replace("%", "%25")
                print("::error file=tests/%s,title=%s::%s" % (f.name, f.name, msg), flush=True)
    print("\n%d 个用例文件：%d 通过，%d 失败" % (len(files), len(files) - len(failed), len(failed)))
    if failed:
        print("失败：" + "、".join(failed))
    if _IN_CI:
        rows = ["## 用例结果", "", "| 用例文件 | 结果 | 失败摘要 |", "|---|---|---|"]
        for f in files:
            ok = f.name not in failed
            rows.append("| %s | %s | %s |" % (f.name, "PASS" if ok else "FAIL",
                                              "" if ok else tails.get(f.name, "").replace("|", "\\|")))
        _summary(rows)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
