# opc-app · OPC 移动端

手机上的 OPC 指挥中心：扫码配对连本机服务端，随时随地看战报、下达任务、做裁决。
视觉稿与设计取舍见 [`design/index.html`](design/index.html)（8 屏）；实现契约见 [`SPEC.md`](SPEC.md)。

## 现在是什么状态

**已能构建出可安装的 debug APK**（`opc-app-v0.1.0-debug.apk`，17.8 MB，44 个 Kotlin 文件 / 约 4.9k 行）：

| 检查项 | 结果 |
|---|---|
| `:app:assembleDebug` | 通过 |
| `:app:testDebugUnitTest`（配对协议 7 例） | 7 passed / 0 failed |
| `:app:lintDebug` | 通过（仅 LockedOrientation / MonochromeLauncherIcon 等无害告警） |
| 模拟器实跑 | 首屏已在 Android 15 (API 35) 模拟器上真实渲染通过，见 `docs/emulator-run-01-connect.png` |
| 主界面纵深验证 | **未做**：本机模拟器不稳定，见下方「模拟器这块的坑」 |

### 已实跑验证的部分

`docs/emulator-run-01-connect.png` 是 Android 15 模拟器上的真实截图：相机取景区（四角描边 + 扫描线）、
「当前网段 10.0.2.0/24 · 已发现服务端 1 台」、手动接入两个输入框、三项预检、红灯提示条、
「配对并连接」主按钮与底部「服务端还没起？先进演示模式」都在位且渲染正常；相机权限申请弹窗正常弹出，
授权后取景区出现真实画面。**安装、冷启动、首帧渲染都不崩。**

### 模拟器这块的坑（不是 App 的问题）

本机模拟器（emulator 37.1.11 + `system-images;android-35;google_apis;x86_64`，Host 为 i7-1360P + Hyper-V）
在 `adb install` 时会打崩 system_server：报 `Failure calling service package: Broken pipe (32)`，
随后 `pm`/`activity`/`window` 服务消失、画面全黑。四次尝试全部落在同一步：

| # | 配置 | 结果 |
|---|---|---|
| 1 | 1080x2400 / 2G / 模拟相机 | 装包成功、界面渲染成功；随后一次 UI 点按把 system_server 打崩 |
| 2 | 1080x2400 / 4G / 4 核 / 无相机 | 装包阶段直接崩 |
| 3 | 720x1560 / 2G / 2 核 / 无相机（`hw.gpu.enabled=no` + swiftshader） | 装包阶段仍然崩 |
| 4 | 同上 + `-wipe-data` | 二次启动再没起来（`bootanim=stopped` 但 `sys.boot_completed` 始终为空） |

结论：**这台机器上的这个模拟器实例不可用于自动化验证** —— 与 App 无关（第 1 轮已证明 App 能装、能渲染）。
下一步要么插真机 `adb install`，要么换机器/换 system image 再验。

**opc-web 那边一个字节都没改** —— 它还没有移动端所需的配对与鉴权接口，
所以本 App 走「在线优先 → 本机缓存 → 演示数据」三级回落：

| 情况 | 表现 |
|---|---|
| 已配对且服务端在线 | 读真实数据（`/api/overview` `/api/queue` `/api/pending` `/api/feed`） |
| 已配对但服务端不可达 | 显示上次缓存 + 顶栏「离线 · 最后同步」提示条 |
| 未配对，点了「先看演示」 | 全套演示数据，顶栏挂「演示数据」标记 |

## 构建

工具链自带在工程内（`.tools/`，已 gitignore），装一次即可，不污染系统环境：

```powershell
pwsh -File scripts/setup-android-sdk.ps1   # 下 JDK 17 + cmdline-tools + platform 35 / build-tools 35
pwsh -File scripts/build-debug.ps1         # 产出 app/build/outputs/apk/debug/app-debug.apk
```

装到手机：`adb install -r app\build\outputs\apk\debug\app-debug.apk`（adb 在 `.tools/android-sdk/platform-tools/`）。

## 工程结构

```
app/src/main/java/com/opc/app/
  domain/       领域模型 + 配对二维码协议（opc://pair?h=&p=&c=）
  data/         DataStore 持久化、Retrofit 接口、仓库（在线优先 + 离线回落）、演示数据
  ui/theme/     金/靛/红三色 + M3 形状与字阶
  ui/components 复用组件（状态条、胶囊芯片、等级标签、指标卡、事件行、气泡、子任务卡）
  ui/screens/   connect / overview / workbench / review / messages / profile
  ui/nav/       底栏五页 + 未配对时强制走连接页
```

## 服务端待补（下一步动 opc-web 时照这个做）

- `OPC_HOST` 允许局域网之外，必须同时补 **设备令牌鉴权**（当前 `127.0.0.1` 是唯一防线）。
- `GET /api/ping` → `{"version":"1.18.0"}`（App 的三项预检与在线探活用）。
- `POST /api/pair`：body `{code, deviceName, deviceCode, platform}` → `{token, deviceCode, serverVersion, projects[]}`；
  配对码一次性、5 分钟有效，成功后本机设备码写入白名单。
- 设置页新增「移动端接入」：展示配对二维码 + 已配对设备列表 + 吊销。
- 鉴权头 `X-OPC-Token`；`opc-config.json` 增 `mobile_devices[]`（设备码/名称/签发时间/吊销位）。

请求/响应字段与 DTO 见 `app/src/main/java/com/opc/app/data/remote/OpcApi.kt`，一一对应。

## 未做（初版有意留白）

- 项目文件 / 知识库独立页（设计上收进「消息」卡片）
- 模型接入、Skill 导入、定时任务、Token 明细等重配置（仍在电脑端做）
- 前台服务与推送：目前是进页面轮询，接下来再做常驻通知
