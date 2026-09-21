package com.opc.app.domain

import java.util.Base64

/**
 * 二维码里的 WireGuard 配置骨架（`wg=` 或逐字段 `wg_*`）。
 *
 * 私钥永远不在这里 —— 服务端不知道手机私钥，所以占位行（`PrivateKey = <由手机生成>`）
 * 或整行缺失都要能解析；手机侧私钥由 [com.opc.app.tunnel.TunnelKeys] 自己生成后覆盖。
 * 任何一个字段坏掉都只让 [parseIni] 返回 null，绝不让整个配对失败。
 */
data class WireConfig(
    val publicKey: String? = null,
    val endpoint: String? = null,
    val address: String? = null,
    val dns: String? = null,
    val allowedIps: String? = null,
    val mtu: Int? = null,
    val keepalive: Int? = null,
) {
    /** 全空等于没拿到隧道信息。 */
    val isEmpty: Boolean
        get() = publicKey == null && endpoint == null && address == null &&
            dns == null && allowedIps == null && mtu == null && keepalive == null
}

/**
 * base64url（无 padding）+ wg-quick INI 的解析。纯 JVM，可单测。
 * 只认 [Interface] 的 Address / DNS / MTU 与 [Peer] 的 PublicKey / Endpoint /
 * AllowedIPs / PersistentKeepalive，其余行忽略（PrivateKey 行也忽略）。
 */
object WireConf {

    fun decodeBase64Url(raw: String): String? {
        val cleaned = raw.trim().replace(' ', '+').replace('-', '+').replace('_', '/')
        if (cleaned.isEmpty()) return null
        val padded = cleaned + "=".repeat((4 - cleaned.length % 4) % 4)
        return runCatching { String(Base64.getDecoder().decode(padded), Charsets.UTF_8) }.getOrNull()
    }

    /** "wg=<base64url>" → WireConfig；解不开、内容不是配置都返回 null。 */
    fun parseEncoded(encoded: String): WireConfig? =
        decodeBase64Url(encoded)?.let { parseIni(it) }?.takeUnless { it.isEmpty }

    fun parseIni(text: String): WireConfig {
        var section = ""
        var publicKey: String? = null
        var endpoint: String? = null
        var address: String? = null
        var dns: String? = null
        var allowedIps: String? = null
        var mtu: Int? = null
        var keepalive: Int? = null

        text.lineSequence().forEach { rawLine ->
            val line = rawLine.substringBefore('#').trim()
            if (line.isEmpty()) return@forEach
            if (line.startsWith("[") && line.endsWith("]")) {
                section = line.substring(1, line.length - 1).trim().lowercase()
                return@forEach
            }
            val key = line.substringBefore('=').trim().lowercase()
            val value = line.substringAfter('=', "").trim()
            if (value.isEmpty()) return@forEach
            when {
                section == "interface" && key == "address" -> address = value
                section == "interface" && key == "dns" -> dns = value
                section == "interface" && key == "mtu" -> mtu = value.toIntOrNull()
                section == "peer" && key == "publickey" -> publicKey = value
                section == "peer" && key == "endpoint" -> endpoint = value
                section == "peer" && key == "allowedips" -> allowedIps = value
                section == "peer" && key == "persistentkeepalive" -> keepalive = value.toIntOrNull()
            }
        }
        return WireConfig(publicKey, endpoint, address, dns, allowedIps, mtu, keepalive)
    }
}
