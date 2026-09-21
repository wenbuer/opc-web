package com.opc.app.tunnel

import com.wireguard.crypto.KeyPair

/**
 * 手机侧密钥对：只在手机生成，私钥永不出设备（配对请求里只有公钥）。
 * 库里是纯 Java 的 Curve25519，不需要 Android，单测可直接跑。
 */
object TunnelKeys {

    /** 返回 (私钥 base64, 公钥 base64)。 */
    fun generate(): Pair<String, String> {
        val pair = KeyPair()
        return pair.privateKey.toBase64() to pair.publicKey.toBase64()
    }
}
