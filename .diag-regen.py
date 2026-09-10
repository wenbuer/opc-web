# 临时：用新结构重新生成 2026-09-10 简报（先备份旧稿对比体积）。
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from opc_web import config, scheduler

p = config.BATCH_ROOT / "每日简报-2026-09-10.md"
old_size = p.stat().st_size if p.is_file() else 0
print("旧简报体积: %.1f KB" % (old_size / 1024))
if p.is_file():
    p.rename(p.with_name(p.name + ".old51kb"))     # 临时改名，让 build 走「当天首份」分支

r = scheduler.build_daily_report(None, "2026-09-10")
print("生成结果:", r.get("ok"), "|", r.get("msg"))
new = config.BATCH_ROOT / "每日简报-2026-09-10.md"
if new.is_file():
    t = new.read_text(encoding="utf-8")
    print("新简报体积: %.1f KB | 行数: %d" % (new.stat().st_size / 1024, len(t.split(chr(10)))))
    print("压缩比: %.0f%%" % (100 - new.stat().st_size / max(old_size, 1) * 100))
    print()
    print("=" * 60)
    print(t[:2600])
else:
    print("!! 未生成")
    bak = config.BATCH_ROOT / "每日简报-2026-09-10.md.old51kb"
    if bak.is_file():
        bak.rename(p)
        print("已还原旧简报")
