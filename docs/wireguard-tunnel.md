# WireGuard 隧道接入（手机 ↔ opc-web）

手机通过 App 内置的 WireGuard 隧道访问 opc-web。**opc-web 继续只监听 `127.0.0.1`**，
不开放局域网、不做 IP 白名单 —— 安全边界在网络层，不在应用层。

## 为什么是隧道而不是"开放局域网 + 白名单"

opc-web 的执行角色手里有 `run_command`（项目根下跑 PowerShell，见 `engines/api.py`），
且全仓**没有任何鉴权**。把监听地址改成 `0.0.0.0` 等于给局域网开一个 RCE 口子，
而基于 IP/MAC 的白名单在局域网里可以伪造。所以：监听地址不动，改用隧道把手机"搬进"回环。

## 两种模式：同一套配置，只有 endpoint 不同

| | 直连模式 | 中继模式 |
|---|---|---|
| 前提 | PC 有公网可达 UDP（公网 IP 或已有端口映射） | PC 在 CGNAT 后，另有一台公网 VPS |
| 手机 endpoint | PC 的公网地址 `x.x.x.x:51820` | VPS 公网地址 `y.y.y.y:51820` |
| PC endpoint | 不设（被动接受握手） | VPS 地址（主动打洞保活） |
| 额外组件 | 无 | VPS 上一份 wg0.conf + ip_forward + FORWARD/NAT |
| App 侧差异 | **无** | **无**（配置全在二维码里） |

App 不区分模式：它只拿到 `endpoint / 公钥 / 自己在该网里的地址`，其余照配。

## 地址规划

隧道网段 `10.9.0.0/24`（只用三个地址，避免和常见家宽网段冲突）：

| 角色 | 隧道地址 | 说明 |
|---|---|---|
| opc-web 所在 PC | `10.9.0.1` | 手机访问 `http://10.9.0.1:8901` |
| VPS 中继 | `10.9.0.2` | 仅中继模式存在 |
| 手机 | `10.9.1.0/24` 顺序分配 | 每台设备一个，可单独吊销 |

## 关键机制：隧道进来的流量怎么落到 127.0.0.1

opc-web 只听回环，所以隧道口收到的包必须转到回环上，落地方案按平台分：

- **Windows（PC）**：`netsh interface portproxy` 把 `10.9.0.1:8901` 转到 `127.0.0.1:8901`。
  由 `opc-web/scripts/mobile-wg-server.ps1` 打印确切命令（脚本只打印，不擅自改系统）。
- **Linux（VPS 只做中继，不跑 opc-web）**：不需要这条 —— 中继只转发，不终止 HTTP。

## 手机侧路由：只隧道一个服务

App 的 `VpnService.Builder` 只加两条路由：服务端隧道地址 `10.9.0.1/32` 与 DNS（如果配置里给了）。
**不加整个网段**，更不加 `0.0.0.0/0` —— 否则手机全部流量绕道 PC，既慢又凭空扩大暴露面。
AllowedIPs 同理，默认 `10.9.0.1/32`。

## App 侧怎么落地（opc-app）

| 文件 | 干什么 |
|---|---|
| `tunnel/OpcTunnelService.kt` | 前台 `VpnService`。继承库自带的 `GoBackend.VpnService`：它的 `onCreate` 会把实例登记进 `GoBackend` 的静态 `CompletableFuture`，`GoBackend` 随后用它拿 `VpnService.Builder` 建 tun、按 AllowedIPs 装路由、拉起 wg |
| `tunnel/TunnelController.kt` | 进程内单例门面：`StateFlow<TunnelUiState>` / `start(profile)` / `stop()` / `reconnect()` |
| `tunnel/WireGuardConfig.kt` | `TunnelProfile` ⇄ wg-quick 文本；AllowedIPs 收窄策略（空→`<服务端隧道地址>/32`，`0.0.0.0/0` 与 `::/0` 一律替换掉） |
| `tunnel/TunnelKeys.kt` | 手机侧密钥对（纯 Java Curve25519），私钥只在手机生成、只落本机 DataStore |

**为什么 manifest 里把库自带的 VpnService 撤掉**：一个 App 只能声明一个带
`android.net.VpnService` intent-filter 的服务，否则 `VpnService.prepare()` 无法确定把授权发给谁。
所以 `AndroidManifest.xml` 用 `tools:node="remove"` 移除
`com.wireguard.android.backend.GoBackend$VpnService`，由 `OpcTunnelService`（同一个类的子类）顶上；
`TunnelController` 在 `GoBackend.setState` 之前先把前台服务起起来，保证库那侧拿到的就是我们的实例。

**启停路径**：配对成功 → `VpnService.prepare` 拿授权 → `start(profile)` →
`startForegroundService(OpcTunnelService)` → `GoBackend.setState(UP, Config)` → 隧道建立；
断开走 `setState(DOWN)`，库自己 `stopSelf()`，前台通知随之撤掉。

**MTU**：配置里不给就用 1420（库自己的默认是 1280，所以一定要显式写进去）。

**构建约束**：APK 只打 `arm64-v8a`（`ndk.abiFilters`）。因此只有 arm64 设备/镜像能装 ——
x86_64 模拟器会因 `INSTALL_FAILED_NO_MATCHING_ABIS` 装不上，隧道要么插真机验，要么临时放开 abiFilters。

## 信任边界

| 组件 | 信任假设 | 失效后果 |
|---|---|---|
| WireGuard 私钥（PC 侧） | 只存本机 `opc-config.json`，权限收紧，不进 git | 私钥泄露 = 别人可以冒充 PC，需要重新生成并给所有手机重新配对 |
| 手机侧私钥 | 只在手机 App 内（Android 应用私有目录） | 手机丢失需在设置页吊销该设备 |
| 配对二维码 | 一次性配对码 TTL 5 分钟、用后即焚 | 5 分钟窗口内被拍到就能抢注，所以别截图外发 |
| VPS 中继 | 只转发 UDP，**看不到明文**（端到端加密） | VPS 被拿下只能丢包/重放，不能解密；但它能拿到双方的公钥与在线时间 |
| App 里的 API 令牌 | 与隧道相互独立：**隧道只负责"能连上"，令牌才决定"能不能用"** | 隧道被攻破仍需令牌，令牌泄露仍需隧道 |

两层是叠加而不是替代：隧道挡住"谁在网络里"，令牌挡住"谁能发指令"。服务端侧令牌改造见
`opc-app/docs/design.md` 与后续的 `/api/mobile/*` 接口。

## 中继 VPS 的最低要求

- 1 核 / 512MB / 10GB 足够（只做 UDP 转发，不做加解密之外的活）。
- 公网 IPv4 + 一个可放行的 UDP 端口（默认 51820）。
- 需要 `net.ipv4.ip_forward=1` 与 FORWARD/NAT 规则，脚本 `opc-web/scripts/mobile-wg-relay.sh` 已含幂等检查。

## 上线检查清单

1. PC 侧服务端配置已生成，私钥权限已收紧（`opc-config.json` 不含明文密钥的副本）；
2. `netsh portproxy` 规则已加（重启后仍在，需 `store=persistent`）；
3. 直连：手机能 `ping 10.9.0.1`；中继：手机与 PC 都显示握手成功（`wg show` 有 latest handshake）；
4. 手机 App 显示"隧道已连接"，访问 `http://10.9.0.1:8901/api/ping` 返回版本号；
5. 断网重连：关掉手机 WiFi 再开，隧道能自动恢复；
6. 吊销一台设备后，该设备**立即**无法握手（服务端 peers 已移除）且无法调用接口（令牌已吊销）。
