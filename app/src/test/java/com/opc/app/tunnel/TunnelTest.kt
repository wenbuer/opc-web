package com.opc.app.tunnel

import com.opc.app.domain.TunnelMode
import com.opc.app.domain.TunnelOffer
import com.opc.app.domain.TunnelProfile
import com.opc.app.domain.WireConfig
import com.wireguard.config.Config
import com.wireguard.crypto.Key
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.StringReader

/**
 * 隧道里不依赖 Android 的那几块：状态机、AllowedIPs 收窄策略、wg-quick 文本。
 * 文本用官方库自己的 Config.parse 回读，保证交给 GoBackend 的确实是它能吃的格式。
 */
class TunnelTest {

    private val wire = WireConfig(
        publicKey = "xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=",
        endpoint = "1.2.3.4:51820",
        address = "10.9.1.7/32",
        dns = "10.9.0.1",
        allowedIps = "10.9.0.1/32",
        mtu = 1420,
        keepalive = 25,
    )

    private fun profile(allowedIps: String = "10.9.0.1/32", endpoint: String = "1.2.3.4:51820") =
        TunnelProfile(
            privateKey = "yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk=",
            publicKey = "HIgo9xNzJMWLKASShiTqIybxZ0U3wGLiUeJ1PKf8ykw=",
            peerPublicKey = "xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=",
            endpoint = endpoint,
            address = "10.9.1.7/32",
            allowedIps = allowedIps,
            mtu = 1420,
            dns = "10.9.0.1",
        )

    // ---------- 状态机 ----------

    @Test
    fun stateMachineWalksIdleToUpToDown() {
        var state = TunnelUiState()
        assertEquals(TunnelState.IDLE, state.state)

        state = state.reduce(TunnelEvent.StartRequested)
        assertEquals(TunnelState.CONNECTING, state.state)
        assertNull(state.lastError)

        state = state.reduce(TunnelEvent.Up)
        assertEquals(TunnelState.UP, state.state)
        assertTrue(state.connected)

        state = state.reduce(TunnelEvent.Down)
        assertEquals(TunnelState.DOWN, state.state)
        assertTrue(!state.connected)
    }

    @Test
    fun failureKeepsReasonAndCanRetry() {
        var state = TunnelUiState().reduce(TunnelEvent.StartRequested)
        state = state.reduce(TunnelEvent.Failed("系统未授权 VPN，隧道没建起来"))
        assertEquals(TunnelState.ERROR, state.state)
        assertEquals("系统未授权 VPN，隧道没建起来", state.lastError)

        // 重试从 ERROR 回到 CONNECTING，旧错误清掉
        state = state.reduce(TunnelEvent.StartRequested)
        assertEquals(TunnelState.CONNECTING, state.state)
        assertNull(state.lastError)
    }

    @Test
    fun labelsMatchDesignCopy() {
        assertEquals("已连接", TunnelUiState(TunnelState.UP).label)
        assertEquals("连接中", TunnelUiState(TunnelState.CONNECTING).label)
        assertEquals("未连接", TunnelUiState(TunnelState.IDLE).label)
        assertEquals("未连接", TunnelUiState(TunnelState.DOWN).label)
        assertEquals("连接失败", TunnelUiState(TunnelState.ERROR).label)
    }

    // ---------- 路由策略 ----------

    @Test
    fun allowedIpsIsAlwaysASingleHostRoute() {
        assertEquals("10.9.0.1/32", WireGuardConfig.normalizeAllowedIp(null, "10.9.0.1"))
        assertEquals("10.9.0.1/32", WireGuardConfig.normalizeAllowedIp("", "10.9.0.1"))
        assertEquals("10.9.0.1/32", WireGuardConfig.normalizeAllowedIp("10.9.0.1", "10.9.0.1"))
        // 默认路由与整段一律换成服务端隧道地址的 /32
        assertEquals("10.9.0.1/32", WireGuardConfig.normalizeAllowedIp("0.0.0.0/0", "10.9.0.1"))
        assertEquals("10.9.0.1/32", WireGuardConfig.normalizeAllowedIp("::/0", "10.9.0.1"))
        // 多条只取第一条
        assertEquals("10.9.0.1/32", WireGuardConfig.normalizeAllowedIp("10.9.0.1/32, 8.8.8.8/32", "10.9.0.1"))
    }

    // ---------- 档案拼装 ----------

    @Test
    fun offerWinsOverQrSkeleton() {
        val offer = TunnelOffer(
            ip = "10.9.1.9",
            cidr = 32,
            serverPublicKey = "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789abcdefg=",
            endpoint = "5.6.7.8:51820",
            allowedIps = "10.9.0.1/32",
            dns = "1.1.1.1",
            mtu = 1280,
        )
        val built = WireGuardConfig.buildTunnelProfile(wire, offer, "priv", "pub", "10.9.0.1")!!
        assertEquals("aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789abcdefg=", built.peerPublicKey)
        assertEquals("5.6.7.8:51820", built.endpoint)
        assertEquals("10.9.1.9/32", built.address)
        assertEquals("1.1.1.1", built.dns)
        assertEquals(1280, built.mtu)
    }

    @Test
    fun qrSkeletonFillsTheGaps() {
        val built = WireGuardConfig.buildTunnelProfile(wire, null, "priv", "pub", "10.9.0.1")!!
        assertEquals("xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=", built.peerPublicKey)
        assertEquals("1.2.3.4:51820", built.endpoint)
        assertEquals(1420, built.mtu)
        assertEquals(25, built.keepalive)
    }

    @Test
    fun missingEssentialsMeansNoTunnel() {
        assertNull(WireGuardConfig.buildTunnelProfile(null, null, "priv", "pub", "10.9.0.1"))
        // 只有地址、没有对端公钥 → 建不起来，配对照旧成功
        assertNull(
            WireGuardConfig.buildTunnelProfile(WireConfig(address = "10.9.1.7/32"), null, "priv", "pub", "10.9.0.1"),
        )
    }

    @Test
    fun mtuDefaultsTo1420() {
        val noMtu = WireConfig(publicKey = wire.publicKey, endpoint = wire.endpoint, address = wire.address)
        assertEquals(1420, WireGuardConfig.buildTunnelProfile(noMtu, null, "priv", "pub", "10.9.0.1")!!.mtu)
    }

    @Test
    fun modeFollowsEndpointHost() {
        // endpoint 就是服务端隧道地址本身 → 直连
        assertEquals(TunnelMode.DIRECT, profile(endpoint = "10.9.0.1:51820").mode)
        assertEquals(TunnelMode.RELAY, profile(endpoint = "5.6.7.8:51820").mode)
    }

    @Test
    fun serverAddressComesFromAllowedIps() {
        assertEquals("10.9.0.1", profile().serverAddress)
    }

    // ---------- 交给官方库的文本 ----------

    @Test
    fun wgQuickTextIsAcceptedByOfficialParser() {
        val text = WireGuardConfig.toWgQuickText(profile())
        val config = Config.parse(StringReader(text).buffered())

        val iface = config.`interface`
        assertEquals("10.9.1.7", iface.addresses.first().address.hostAddress)
        assertEquals(32, iface.addresses.first().mask)
        assertEquals("10.9.0.1", iface.dnsServers.first().hostAddress)
        assertEquals(1420, iface.mtu.get())

        val peer = config.peers.first()
        assertEquals("xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=", peer.publicKey.toBase64())
        assertEquals("1.2.3.4", peer.endpoint.get().host)
        assertEquals(51820, peer.endpoint.get().port)
        assertEquals("10.9.0.1", peer.allowedIps.first().address.hostAddress)
        assertEquals(32, peer.allowedIps.first().mask)
    }

    @Test
    fun wgQuickTextOmitsOptionalDnsAndKeepalive() {
        val text = WireGuardConfig.toWgQuickText(profile().copy(dns = null, keepalive = null))
        val config = Config.parse(StringReader(text).buffered())
        assertTrue(config.`interface`.dnsServers.isEmpty())
        assertTrue(!config.peers.first().persistentKeepalive.isPresent)
    }

    // ---------- 密钥 ----------

    @Test
    fun keyPairIsGeneratedOnDevice() {
        val (privateKey, publicKey) = TunnelKeys.generate()
        assertNotNull(Key.fromBase64(privateKey))
        assertNotNull(Key.fromBase64(publicKey))
        assertTrue(privateKey != publicKey)

        // 两次生成不一样，避免复用同一把
        assertTrue(privateKey != TunnelKeys.generate().first)
    }
}
