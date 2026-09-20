package com.opc.app.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** 这是全工程唯一一段「自己写的解析逻辑」，用测试把协议边界钉住。 */
class QrProtocolTest {

    @Test
    fun opcSchemeWithHostPortAndCode() {
        val t = QrProtocol.parse("opc://pair?h=192.168.1.20&p=8901&c=K7QP-3M2X&v=1.18.0")
        assertNotNull(t)
        assertEquals("http://192.168.1.20:8901", t!!.baseUrl)
        assertEquals("K7QP-3M2X", t.code)
        assertEquals("1.18.0", t.serverVersion)
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
        // 没有点号的输入不是可达地址
        assertNull(QrProtocol.manual("不是地址", "ABCD"))
        assertNull(QrProtocol.manual("192.168.1.20", "  "))
    }

    @Test
    fun deviceCodeFormat() {
        val code = QrProtocol.newDeviceCode()
        assertTrue(code, code.startsWith("DEV-"))
        assertEquals(13, code.length)
    }
}
