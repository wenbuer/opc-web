# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：onedir 分发（dist/opc-web/ 整个目录即为可运行产物）。

数据文件全部写进 datas，所以产物**自包含**，不需要构建后再拷贝一遍资源：
- templates / static：控制台界面（HTML + CSS + JS）
- agents-seed：新项目的角色卡种子

刻意**不捆绑 dsh 运行时**：默认引擎是直连大模型 API，开箱即用；dsh 包 190MB 上下，
塞进来只会让发布包臃肿。要用 DSH 引擎，本机装 node + @deepseek-ai/dsh 即可，
或用 build.ps1 -WithDsh 单独出一个带 dsh 的版本。

资源落位（PyInstaller 6.x onedir 默认）在 exe 同级的 _internal/ 下，运行时代码用
config.ASSET 找它们（见 config.py）。
"""
import os
import sys

# collect_submodules 要能真正 import 到包才收集得到 —— 求值 spec 时 sys.path 里还没有
# src/（pathex 只作用于 Analysis 的搜索），不补这一步会静默收集到空列表，
# 打包出来的 exe 一调引擎就 ModuleNotFoundError。
_src = os.path.join(SPECPATH, 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('opc_web')
# 双保险：两个引擎实现是 registry 用 importlib 动态导入的，静态分析看不见它们。
hiddenimports += ['opc_web.engines.dsh', 'opc_web.engines.api',
                  'zstandard']      # 有 C 扩展，显式声明更稳


a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('agents-seed', 'agents-seed'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='opc-web',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='opc-web',
)
