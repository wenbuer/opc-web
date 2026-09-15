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
- **但 exec_state 非空 ≠ 真有任务在跑**：dsh 的会话监听线程比 `finished` 晚一步退出，它最后一次心跳会在完成后把条目重建出来（`startedAt` 是完成时刻、`elapsed` 却是真实运行时长，两者对不上就是这个指纹）。判据换成「服务有没有活着的 headless 子进程」（`Get-CimInstance Win32_Process` 里 parent 是服务器 pid 的 node）—— 幽灵条目只挡归档，重启正好清掉它。T-028-S2 因此卡在「执行中」不回
- **把「查」和「重启」写进同一条命令，让它自己拦**。分开两步就会出事：我先打印了状态、看见 `busy=true, tag=执行 1/3`，然后那条命令照样往下走、把正在跑的子任务杀了 —— 一个上午连犯两次。用下面这段，闸不过就 `exit 1`，重启根本不会执行：

```powershell
$s = (Invoke-WebRequest 'http://127.0.0.1:8901/api/scheduler' -TimeoutSec 10 -UseBasicParsing).Content | ConvertFrom-Json
$srv = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*run.py*' })
$kids = 0
foreach ($p in $srv) { $kids += @(Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $p.ProcessId -and $_.Name -eq 'node.exe' }).Count }
if ($s.state.busy -or $kids -gt 0) { "拒绝重启：busy=" + $s.state.busy + " headless=" + $kids + " tag=" + $s.state.tag; exit 1 }
foreach ($p in $srv) { taskkill /PID $p.ProcessId /F 2>&1 | Out-Null }
Start-Sleep -Seconds 2
python opc-web/scripts/scratch_serve.py
```

  （`busy` 是任务级；`headless>0` 是子任务级 —— **两个都要看**。队列里「排队」的任务不算在跑，不会被拦。）

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
