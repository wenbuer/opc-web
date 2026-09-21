# 配对与隧道协议契约（v1）

App 与服务端各实现一半，字段名、格式、失败语义都在这里定死。改协议先改这份文档。

## 1. 二维码内容

```
opc://pair?h=<host>&p=<port>&c=<配对码>&wg=<base64url(conf)>&v=<服务端版本>
```

| 参数 | 必填 | 含义 |
|---|---|---|
| `h` | 是 | **手机要访问的地址**。有隧道时填隧道地址 `10.9.0.1`，没有隧道时填局域网地址 |
| `p` | 是 | 端口，默认 8901 |
| `c` | 是 | 一次性配对码，6 位大写字母数字（去掉 0/O/1/I） |
| `wg` | 否 | base64url（无 padding）编码的 WireGuard 配置文本 |
| `v` | 否 | 服务端版本，仅用于展示 |

**逐字段兜底形式**（对方不方便拼 conf 时）：`wg_pub`、`wg_ep`、`wg_ip`、`wg_dns`、`wg_allowed`、`wg_mtu`，
语义与 conf 里对应字段一致。两种形式同时出现时，`wg` 优先。

## 2. wg 配置文本（手机侧）

标准 `wg-quick` 能读的格式，App 只需解析 `[Interface]` 的 `Address/DNS/MTU`、`[Peer]` 的 `PublicKey/Endpoint/AllowedIPs/PersistentKeepalive`：

```ini
[Interface]
PrivateKey = <手机侧私钥，由手机自己生成>
Address = 10.9.1.7/32
MTU = 1420
DNS = 10.9.0.1            # 可选，不给就不配 DNS

[Peer]
PublicKey = <PC 或 VPS 的公钥>
Endpoint = <IP:端口>       # 直连=PC 公网，中继=VPS 公网
AllowedIPs = 10.9.0.1/32   # 只隧道 opc-web，不放整段
PersistentKeepalive = 25   # 中继模式必需，直连可选
```

**PrivateKey 永不出现在二维码里** —— 私钥由手机生成，只上传公钥。

## 3. 配对流程（两次网络往返）

```
手机                                        服务端
 │ 扫码得到 opc://pair?...（含 wg 配置骨架、不含手机私钥/公钥）
 │ 生成手机侧密钥对
 │── POST /api/pair {code, deviceName, deviceCode, platform, publicKey} ──▶  校验配对码（单次、5 分钟 TTL）
 │                                                                          分配隧道 IP、写 mobile_devices[]
 │◀─ 200 {token, deviceCode, serverVersion, tunnel: {ip, cidr, serverPublicKey, endpoint, allowedIps, dns, mtu}, projects[]} ──
 │ 用返回的隧道参数补全 conf，拉起 VpnService
 │── POST /api/mobile/device/confirm {deviceCode} ──▶  标记"已启用"，服务端 wg 接口加上这个 peer
```

要点：
- **服务端只存公钥与令牌哈希**，任何私钥都不上传；
- 配对码校验失败要按来源退避，且**失败原因不区分**（"码不存在"与"码已过期"返回同一提示，避免枚举）；
- `confirm` 之前 peer 是"待确认"状态：允许握手与 `/api/ping`，不允许 dispatch/piyue；确认后才放行写接口。

## 4. 鉴权

- 所有接口（除 `GET /api/ping`、`POST /api/pair`）要求请求头 `X-OPC-Token: <token>`；
- 服务端存 sha256 哈希，比较用常量时间；令牌 30 天滚动续期，每次成功请求刷新最后使用时间；
- 401 与 403 分开：401=没令牌/令牌无效，403=令牌有效但该设备被吊销或未 confirm。

## 5. 失败语义（App 侧要能区分并给出不同提示）

| 情况 | HTTP | App 提示 |
|---|---|---|
| 配对码错误/过期 | 400 | 配对码无效或已过期，请在服务端重新生成 |
| 设备未在服务端登记 | 403 | 本机未授权，请在服务端「移动端接入」加入本设备 |
| 令牌被吊销 | 401 | 授权已失效，请重新扫码配对 |
| 服务端不可达 | — | 显示离线缓存 + 顶栏提示，保留重连按钮 |
| 隧道未建立 | — | 提示"隧道未连接"，点击可重连；不要误报为"服务端不在线" |

## 6. 兼容性

- 老二维码（无 `wg`）必须仍能配对，只是不进隧道、直连局域网地址 —— 这样服务端升级前生成的码不会失效；
- 服务端返回未知字段时 App 忽略，不报错（`ignoreUnknownKeys` 已开）。
