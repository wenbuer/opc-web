package com.opc.app.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** 这是全工程唯一一段「自己写的解析逻辑」，用测试把协议边界钉住。 */
class QrProtocolTest {

    /** 服务端生成的 wg 骨架（base64url 无 padding，含 PrivateKey 占位行）。 */
    private val confBase64 = "W0ludGVyZmFjZV0KUHJpdmF0ZUtleSA9IDznlLHmiYvmnLrnlJ_miJA-" +
        "CkFkZHJlc3MgPSAxMC45LjEuNy8zMgpNVFUgPSAxNDIwCkROUyA9IDEwLjkuMC4xCgpbUGVlcl0K" +
        "UHVibGljS2V5ID0geFRJQkE1cmJvVXZuSDRodG9kamI2ZTY5N1FqTEVSdDFOQUI0bVpxcDhEZz0K" +
        "RW5kcG9pbnQgPSAxLjIuMy40OjUxODIwCkFsbG93ZWRJUHMgPSAxMC45LjAuMS8zMgpQZXJzaXN0" +
        "ZW50S2VlcGFsaXZlID0gMjUK"

    @Test
    fun opcSchemeWithHostPortAndCode() {
        val t = QrProtocol.parse("opc://pair?h=192.168.1.20&p=8901&c=K7QP-3M2X&v=1.18.0")
        assertNotNull(t)
        assertEquals("http://192.168.1.20:8901", t!!.baseUrl)
        assertEquals("K7QP-3M2X", t.code)
        assertEquals("1.18.0", t.serverVersion)
        // 老二维码没有 wg，照样能配，只是不进隧道
        assertNull(t.wire)
    }

    @Test
    fun opcSchemeDefaultsPortWhenMissing() {
        val t = QrProtocol.parse("opc://pair?h=10.0.0.7&c=ABCD-1234")
        assertEquals("http://10.0.0.7:8901", t!!.baseUrl)
    }

    @Test
    fun httpUrlFormIsAccepted() {
        val t = QrProtocol.parse("http://192.168.1.20:8901/pair?c=K7QP-3M2X")
        assertEquals("http://192.168.1.20:8901", t!!.baseUrl)
        assertEquals("K7QP-3M2X", t.code)
    }

    @Test
    fun missingCodeIsRejected() {
        assertNull(QrProtocol.parse("opc://pair?h=192.168.1.20&p=8901"))
        assertNull(QrProtocol.parse("https://example.com/whatever"))
    }

    @Test
    fun junkIsRejected() {
        assertNull(QrProtocol.parse(""))
        assertNull(QrProtocol.parse("just some text"))
        assertNull(QrProtocol.parse("opc://pair?p=8901&c=X"))
    }

    @Test
    fun manualInputNormalizesAddress() {
        val t = QrProtocol.manual("192.168.1.20", "k7qp-3m2x")
        assertEquals("http://192.168.1.20:8901", t!!.baseUrl)
        assertEquals("K7QP-3M2X", t.code)

        val t2 = QrProtocol.manual("http://192.168.1.20:9000", "ABCD")
        assertEquals("http://192.168.1.20:9000", t2!!.baseUrl)
        // 不是主机名字符集（中文）才拒绝
        assertNull(QrProtocol.manual("不是地址", "ABCD"))
        assertNull(QrProtocol.manual("192.168.1.20", "  "))
    }

    /** 主机名允许不带点号：局域网里的 pc-name 也要能连。 */
    @Test
    fun dotlessHostnameIsAccepted() {
        assertEquals("http://pc-name:8901", PairAddress.normalize("pc-name"))
        assertEquals("http://pc-name:8901", PairAddress.normalize("pc-name:8901"))
        assertEquals("http://pc-name:8901", PairAddress.normalize("http://pc-name:8901/pair?c=1"))
        assertEquals("http://opc-pc-01:8901", QrProtocol.manual("opc-pc-01", "ABCD")!!.baseUrl)
        // 隧道地址与域名行为不变
        assertEquals("http://10.9.0.1:8901", PairAddress.normalize("10.9.0.1"))
        assertEquals("http://opc.local:8901", PairAddress.normalize("opc.local:8901"))
        // 空串与非主机名字符一律拒绝
        assertNull(PairAddress.normalize(""))
        assertNull(PairAddress.normalize("   "))
        assertNull(PairAddress.normalize("http://"))
        assertNull(PairAddress.normalize("http://:8901"))
        assertNull(PairAddress.normalize("host name:8901"))
    }

    /** wg= 整份 conf：h 是手机要访问的隧道地址，endpoint 另给。 */
    @Test
    fun qrCarriesWireGuardConf() {
        val t = QrProtocol.parse("opc://pair?h=10.9.0.1&p=8901&c=K7QP-3M2X&wg=" + confBase64 + "&v=1.18.0")
        assertNotNull(t)
        assertEquals("http://10.9.0.1:8901", t!!.baseUrl)
        val wire = t.wire
        assertNotNull(wire)
        assertEquals("xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=", wire!!.publicKey)
        assertEquals("1.2.3.4:51820", wire.endpoint)
        assertEquals("10.9.1.7/32", wire.address)
        assertEquals("10.9.0.1/32", wire.allowedIps)
        assertEquals("10.9.0.1", wire.dns)
        assertEquals(1420, wire.mtu)
        assertEquals(25, wire.keepalive)
    }

    /** 逐字段兜底形式。 */
    @Test
    fun qrCarriesWireGuardFieldsFallback() {
        val t = QrProtocol.parse(
            "opc://pair?h=10.9.0.1&c=K7QP-3M2X&wg_pub=xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=" +
                "&wg_ep=5.6.7.8:51820&wg_ip=10.9.1.9/32&wg_dns=10.9.0.1&wg_allowed=10.9.0.1/32&wg_mtu=1280",
        )
        val wire = t!!.wire
        assertNotNull(wire)
        assertEquals("5.6.7.8:51820", wire!!.endpoint)
        assertEquals("10.9.1.9/32", wire.address)
        assertEquals("10.9.0.1", wire.dns)
        assertEquals("10.9.0.1/32", wire.allowedIps)
        assertEquals(1280, wire.mtu)
        assertNull(wire.keepalive)
    }

    /** wg 坏掉只丢隧道，配对本身不能失败。 */
    @Test
    fun brokenWireConfigDoesNotBreakPairing() {
        val t = QrProtocol.parse("opc://pair?h=192.168.1.20&c=K7QP-3M2X&wg=%25%25not-base64%25%25")
        assertNotNull(t)
        assertEquals("http://192.168.1.20:8901", t!!.baseUrl)
        assertNull(t.wire)
    }

    /** wg 解不开时，逐字段那套仍然兜底。 */
    @Test
    fun fieldsStillWorkWhenConfIsBroken() {
        val t = QrProtocol.parse("opc://pair?h=10.9.0.1&c=K7QP-3M2X&wg=!!!&wg_ep=5.6.7.8:51820")
        assertEquals("5.6.7.8:51820", t!!.wire!!.endpoint)
    }

    @Test
    fun deviceCodeFormat() {
        val code = QrProtocol.newDeviceCode()
        assertTrue(code, code.startsWith("DEV-"))
        assertEquals(13, code.length)
    }
}
