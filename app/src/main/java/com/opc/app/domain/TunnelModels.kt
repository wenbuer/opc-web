package com.opc.app.domain

/**
 * 服务端在 `POST /api/pair` 响应里下发的隧道参数（contract §3 的 `tunnel{}`）。
 * 手机侧私钥不在其中 —— 私钥由手机生成，只上传公钥。
 */
data class TunnelOffer(
    val ip: String? = null,
    val cidr: Int = 32,
    val serverPublicKey: String? = null,
    val endpoint: String? = null,
    val allowedIps: String? = null,
    val dns: String? = null,
    val mtu: Int? = null,
)

/** 模式只用于展示：endpoint 就是服务端隧道地址本身 → 直连，否则走公网中转。 */
enum class TunnelMode(val label: String) {
    DIRECT("直连"),
    RELAY("中继"),
}

/**
 * 完整的隧道档案：二维码骨架 + 响应参数 + 手机自己生成的密钥对，落本机 DataStore。
 * allowedIps 只放服务端隧道地址的一条 /32 —— 不放整段，更不放 0.0.0.0/0。
 */
data class TunnelProfile(
    val privateKey: String,
    val publicKey: String,
    val peerPublicKey: String,
    val endpoint: String,
    val address: String,
    val allowedIps: String,
    val mtu: Int,
    val dns: String? = null,
    val keepalive: Int? = null,
) {
    /** 手机要访问的服务端隧道地址（被隧道的那条路由）。 */
    val serverAddress: String
        get() = allowedIps.substringBefore(',').trim().substringBefore('/')

    val endpointHost: String
        get() = endpoint.substringBeforeLast(':', endpoint)

    val mode: TunnelMode
        get() = if (endpointHost == serverAddress) TunnelMode.DIRECT else TunnelMode.RELAY
}
