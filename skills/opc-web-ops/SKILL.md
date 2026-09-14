---
name: opc-web-ops
description: opc-web 控制台的本地运维：起服务、重启时机、截图验证、Windows 方括号路径坑。当需要重启服务、截图验证界面、或排查"服务挂了"时加载。
---

# opc-web 运维手册

## 起服务：scripts/scratch_serve.py

三个坑都踩过，别再改：

| 启动方式 | 子进程能继承控制台 | 弹窗 | 被 ^C 带走 |
|---|---|---|---|
| 挂当前控制台（Start-Process） | 能 | 否 | **会** |
| `DETACHED_PROCESS` | **不能** | **会** | 否 |
| **`CREATE_NEW_CONSOLE` + `SW_HIDE`（现用）** | 能 | 否 | 否 |

- 被 ^C 带走的表现：`logs/server.err.log` 里只有一个 `^C`
- 无控制台的表现：dsh 每次调 `pwsh` 工具都弹一个窗（子进程没有控制台可继承，Windows 给它们各新建一个）

## 重启时机（这项最贵）

- **纯前端改动不重启**：改 `static/*.css|js` 或 `templates/index.html`，递增其中的 `?v=`，用户 Ctrl+F5 即可
- **只有改了 `src/opc_web/*.py` 才重启**
- **重启前先查有没有在跑的任务**：`runner.exec_state()` 非空就别重启——会打断正在执行的任务。T-021 曾因此重跑一遍，多烧 271 万 token

## 动手前先探活

```powershell
Invoke-WebRequest 'http://127.0.0.1:8901/' -UseBasicParsing -TimeoutSec 10
```

失败先看 `logs/server.err.log`，**别急着怀疑自己刚改的代码**（本会话 3 次"服务挂了"都是最后才发现，白排查一轮）。

## 截图验证套路

1. 备份 `templates/index.html` 内容并记 sha256
2. 在 `</body>` 前注入探针 `<script>`（自动切 tab / 点按钮 / 拖拽）
3. Edge headless：
   `--headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=9000 --screenshot=X.png --window-size=W,H`
4. **还原 index.html 并校验 sha256**（放 `finally`，否则产品页被改成探针页）
5. 探针文件用 `_` 前缀，用完即删（`_*.png` / `_*.html` 已 gitignore）

**优先用文本断言代替截图**：探针把结论打印出来（如 `拖动前 left=1098 拖动后 left=938 可拖动 OK`），比 200-300KB 的截图省得多。只有布局/视觉才需要真截图。

## Windows 方括号路径（本项目路径含 `[2608]`）

- 所有 path 参数用 `-LiteralPath`
- `Start-Process -RedirectStandardOutput/-RedirectStandardError` 会把路径当通配符 → 报 `wildcard path did not resolve` → 让脚本自己 `open()` 文件，或经 `cmd /c` 转发
- `Join-Path` 的第二个位置参数在本机解析异常 → 用字符串插值 `"$Root\dist\x"`
