package com.opc.app.data

/**
 * 配对/鉴权的失败语义（docs/pairing-protocol.md §5）。
 * 契约要求 400 / 401 / 403 给不同提示，服务端也按这个分；纯函数，可单测。
 */
object PairFailure {

    /** 隧道没起来：不能报成「服务端不在线」。 */
    const val TUNNEL_DOWN = "隧道未连接，先建立隧道再配对"

    fun hint(httpCode: Int?): String = when (httpCode) {
        400 -> "配对码无效或已过期，请在服务端重新生成"
        401 -> "授权已失效，请重新扫码配对"
        403 -> "本机未授权，请在服务端「移动端接入」加入本设备"
        null -> "服务端不可达，检查网络或隧道"
        else -> "配对被拒绝（HTTP " + httpCode + "）"
    }
}
