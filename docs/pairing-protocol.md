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

## 6. 内容读取（知识库 / 产出 / 回报）

手机要读的是**纯文本 markdown**，服务端已有对应实现（`knowledge.read_md`、`scheduler.ws_read`、
`scheduler.task_output`、`knowledge.kb_entries`），移动端复用它们，只加一层更顺手的收口：

| 接口 | 参数 | 返回 |
|---|---|---|
| `GET /api/mobile/docs/index` | `role`（可选） | `{groups: [{role, files: [{rel, name, size, mtime}]}]}` —— 工作区产物清单，只列 .md |
| `GET /api/mobile/docs/read` | `rel`（必填，工作区内相对路径） | `{rel, name, kind: "md"\|"txt", text, sha256}` |
| `GET /api/mobile/docs/output` | `no`（任务号） | `{no, reports: [...], files: [{rel, name, text}], log}` |
| `GET /api/mobile/kb/index` | — | `{entries: [{title, rel, topic, updatedAt}]}` |
| `GET /api/mobile/kb/read` | `rel` | 同 `docs/read` |

要点：
- **鉴权与设备状态同其他移动端接口**：需 `X-OPC-Token`，且设备必须已 confirm（未确认 403）。
- `rel` 一律走服务端既有的路径越界校验（`resolve()` 后必须在项目根内），移动端**不得**自行拼接绝对路径。
- 单文件上限沿用服务端的 `_WS_MAX_BYTES`；超限返回 413 而不是截断（截断会让阅读者以为文章写完了）。
- `sha256` 用于客户端缓存失效判断与（将来的）解密后完整性校验。

## 7. 内容传输的加密

分两件事，不要混为一谈：

| 层 | 现状 | 结论 |
|---|---|---|
| 链路加密 | WireGuard 隧道（ChaCha20-Poly1305）已覆盖；不连隧道时是明文 HTTP | **连隧道时已够**；不连隧道再谈加 TLS |
| 内容加密 | 无 | 见下面三种取法，未定 |

三种取法的代价：

1. **TLS + 证书固定**（推荐先做）：服务端自签 CA 签一张证书，App 内置该 CA 公钥做 pinning。
   解决"被中继/同网段窃听与篡改"。服务端仍能看到明文。
2. **内容在服务端加密存储，手机持私钥**：web 端用手机公钥加密文档、密文落盘。
   **代价：R1 与执行角色读不了知识库** —— 现有"知识沉淀与合并"流程会失效。
   只有在"服务端本身不可信"时才值得付这个代价。
3. **EC3 折中**（本机文件仍明文、对手机单独密文）：安全上等价于 1 + 静态加密，复杂度最高，不推荐。

客户端实现留了接缝：仓库层的读取方法返回**已解密文本**，解密与否由 `ContentCodec` 决定
（当前是恒等实现）。将来换 EC1 时它不变，换 EC2 时只改这一个类。

## 8. 兼容性

- 老二维码（无 `wg`）必须仍能配对，只是不进隧道、直连局域网地址 —— 这样服务端升级前生成的码不会失效；
- 服务端返回未知字段时 App 忽略，不报错（`ignoreUnknownKeys` 已开）。
