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
# 注意：PyInstaller 6.x 把 spec 里的**相对路径按 SPECPATH（scripts/）解析**，不是按 CWD。
# 所以 run.py 与 agents-seed 都必须用 _root 拼绝对路径 —— 写成 'run.py' 会去找
# scripts/run.py 直接报 not found；写成 ('agents-seed','agents-seed') 更糟：不报错，静静打进空目录。
_root = os.path.normpath(os.path.join(SPECPATH, '..'))   # spec 在 scripts/ 下，资源根是上一层
_src = os.path.join(_root, 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('opc_web')
# 双保险：两个引擎实现是 registry 用 importlib 动态导入的，静态分析看不见它们。
hiddenimports += ['opc_web.engines.dsh', 'opc_web.engines.api',
                  'zstandard']      # 有 C 扩展，显式声明更稳


a = Analysis(
    [os.path.join(_root, 'run.py')],
    pathex=[_src],
    binaries=[],
    # datas 只放「随包分发的程序资源」，**刻意不含**下面这些（加了就是把别人的东西发出去）：
    #   skills / ~/.dsh/skills —— 本机技能是使用者自己的，运行时按需扫描即可，不进包
    #   agents/、工作区/、批阅台/、知识库/、项目/、opc-data/ —— 项目运行数据
    #   .env、opc-config.json —— 本机配置与密钥
    # agents-seed 要进包：角色卡与《员工手册》的源就在那儿（handbook_text 从它读），
    # 但**不从使用者的项目里**拷任何东西。
    datas=[
        (os.path.join(_root, 'templates'), 'templates'),
        (os.path.join(_root, 'static'), 'static'),
        (os.path.join(_root, 'agents-seed'), 'agents-seed'),
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
