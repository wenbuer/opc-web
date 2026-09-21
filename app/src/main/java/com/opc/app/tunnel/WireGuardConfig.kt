package com.opc.app.tunnel

import com.opc.app.domain.TunnelOffer
import com.opc.app.domain.TunnelProfile
import com.opc.app.domain.WireConfig

/**
 * TunnelProfile ⇄ wg-quick 文本的纯逻辑（不碰 Android，可单测）。
 *
 * 路由策略钉在这里：AllowedIPs 永远只放「服务端隧道地址」的一条 /32。
 * 官方 GoBackend 会照着 Config 里的 AllowedIPs 逐条 addRoute，所以这里收窄了，
 * 手机侧就不会为整个网段（更不会为 0.0.0.0/0）改路由表。
 */
object WireGuardConfig {

    const val DEFAULT_MTU = 1420

    /** 把任意写法的 AllowedIPs 收成单条：空则用服务端隧道地址 /32，整段/默认路由一律拒掉。 */
    fun normalizeAllowedIp(raw: String?, fallbackHost: String): String {
        val first = raw?.split(',')?.firstOrNull { it.trim().isNotEmpty() }?.trim().orEmpty()
        val candidate = when {
            first.isEmpty() -> fallbackHost + "/32"
            '/' in first -> first
            else -> first + "/32"
        }
        return if (candidate == "0.0.0.0/0" || candidate == "::/0") fallbackHost + "/32" else candidate
    }

    private fun withMask(address: String): String =
        if ('/' in address) address else address + "/32"

    /**
     * 响应参数优先、二维码骨架兜底；peer 公钥/endpoint/手机地址三样缺一就返回 null
     * （返回 null = 不进隧道，配对照旧成功）。
     */
    fun buildTunnelProfile(
        wire: WireConfig?,
        offer: TunnelOffer?,
        privateKey: String,
        publicKey: String,
        fallbackServerHost: String,
    ): TunnelProfile? {
        val peer = offer?.serverPublicKey?.takeIf { it.isNotBlank() } ?: wire?.publicKey
        val endpoint = offer?.endpoint?.takeIf { it.isNotBlank() } ?: wire?.endpoint
        val address = offer?.ip?.takeIf { it.isNotBlank() }?.let { it + "/" + offer.cidr } ?: wire?.address
        if (peer.isNullOrBlank() || endpoint.isNullOrBlank() || address.isNullOrBlank()) return null
        val allowed = normalizeAllowedIp(
            offer?.allowedIps?.takeIf { it.isNotBlank() } ?: wire?.allowedIps,
            fallbackServerHost,
        )
        val mtu = offer?.mtu?.takeIf { it > 0 } ?: wire?.mtu?.takeIf { it > 0 } ?: DEFAULT_MTU
        return TunnelProfile(
            privateKey = privateKey,
            publicKey = publicKey,
            peerPublicKey = peer,
            endpoint = endpoint,
            address = withMask(address),
            allowedIps = allowed,
            mtu = mtu,
            dns = offer?.dns?.takeIf { it.isNotBlank() } ?: wire?.dns?.takeIf { it.isNotBlank() },
            keepalive = wire?.keepalive?.takeIf { it > 0 },
        )
    }

    /** 交给 com.wireguard.config.Config.parse 的文本。PrivateKey 用手机自己生成的那把。 */
    fun toWgQuickText(profile: TunnelProfile): String = buildString {
        appendLine("[Interface]")
        appendLine("PrivateKey = " + profile.privateKey)
        appendLine("Address = " + withMask(profile.address))
        appendLine("MTU = " + profile.mtu)
        profile.dns?.let { appendLine("DNS = " + it) }
        appendLine()
        appendLine("[Peer]")
        appendLine("PublicKey = " + profile.peerPublicKey)
        appendLine("Endpoint = " + profile.endpoint)
        appendLine("AllowedIPs = " + profile.allowedIps)
        profile.keepalive?.let { appendLine("PersistentKeepalive = " + it) }
    }
}
