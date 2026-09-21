package com.opc.app.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * 二维码里的 wg 骨架解析。契约要求两种形态都能吃下：
 *  - `wg=` base64url（手机自己生成私钥，所以文里可能是占位行，也可能整行都没有）
 *  - 逐字段 `wg_*`
 * 解析失败只丢隧道，绝不能让配对失败。
 */
class WireConfTest {

    /** 服务端会生成的那份骨架（含 PrivateKey 占位行），base64url 无 padding。 */
    private val encodedWithPlaceholder = "W0ludGVyZmFjZV0KUHJpdmF0ZUtleSA9IDznlLHmiYvmnLrnlJ_miJA-" +
        "CkFkZHJlc3MgPSAxMC45LjEuNy8zMgpNVFUgPSAxNDIwCkROUyA9IDEwLjkuMC4xCgpbUGVlcl0K" +
        "UHVibGljS2V5ID0geFRJQkE1cmJvVXZuSDRodG9kamI2ZTY5N1FqTEVSdDFOQUI0bVpxcDhEZz0K" +
        "RW5kcG9pbnQgPSAxLjIuMy40OjUxODIwCkFsbG93ZWRJUHMgPSAxMC45LjAuMS8zMgpQZXJzaXN0" +
        "ZW50S2VlcGFsaXZlID0gMjUK"

    private val plainText = """
        [Interface]
        Address = 10.9.1.7/32
        MTU = 1420
        DNS = 10.9.0.1

        [Peer]
        PublicKey = xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=
        Endpoint = 10.9.0.1:51820
        AllowedIPs = 10.9.0.1/32
        PersistentKeepalive = 25
    """.trimIndent()

    @Test
    fun base64UrlConfIsDecoded() {
        val wire = WireConf.parseEncoded(encodedWithPlaceholder)
        assertNotNull(wire)
        assertEquals("xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=", wire!!.publicKey)
        assertEquals("1.2.3.4:51820", wire.endpoint)
        assertEquals("10.9.1.7/32", wire.address)
        assertEquals("10.9.0.1", wire.dns)
        assertEquals("10.9.0.1/32", wire.allowedIps)
        assertEquals(1420, wire.mtu)
        assertEquals(25, wire.keepalive)
    }

    /** 契约第 4 条：没有 PrivateKey 行也必须能解析（私钥由手机生成后覆盖）。 */
    @Test
    fun confWithoutPrivateKeyLineIsAccepted() {
        val wire = WireConf.parseIni(plainText)
        assertEquals("xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=", wire.publicKey)
        assertEquals("10.9.0.1:51820", wire.endpoint)
        assertEquals("10.9.1.7/32", wire.address)
        assertEquals(1420, wire.mtu)
    }

    @Test
    fun placeholderPrivateKeyIsIgnored() {
        // 占位行不参与解析，也不影响其它字段
        val wire = WireConf.parseIni(
            "[Interface]\nPrivateKey = <由手机生成>\nAddress = 10.9.1.7/32\n[Peer]\n" +
                "PublicKey = abcdefg=\nEndpoint = 1.1.1.1:51820\nAllowedIPs = 10.9.0.1/32\n",
        )
        assertEquals("10.9.1.7/32", wire.address)
        assertEquals("abcdefg=", wire.publicKey)
    }

    @Test
    fun commentsAndUnknownKeysAreSkipped() {
        val wire = WireConf.parseIni(
            "# 这是注释\n[Interface]\nAddress = 10.9.1.7/32  # 内联注释\nListenPort = 51821\n",
        )
        assertEquals("10.9.1.7/32", wire.address)
        assertNull(wire.publicKey)
    }

    @Test
    fun brokenInputYieldsNullNotCrash() {
        assertNull(WireConf.parseEncoded("这不是 base64"))
        assertNull(WireConf.parseEncoded(""))
        // 解出来是空内容 → 视为没拿到隧道，而不是抛异常
        val empty = java.util.Base64.getUrlEncoder().withoutPadding().encodeToString("hello world".toByteArray())
        assertNull(WireConf.parseEncoded(empty))
    }

    @Test
    fun emptyConfigIsRecognised() {
        assertEquals(true, WireConf.parseIni("[Interface]\n").isEmpty)
    }
}
