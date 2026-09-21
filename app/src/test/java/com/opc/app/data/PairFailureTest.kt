package com.opc.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** 契约 §5：五种失败要能分辨，不能都糊成「配对失败」。 */
class PairFailureTest {

    @Test
    fun httpCodesMapToDistinctHints() {
        val invalid = PairFailure.hint(400)
        val revoked = PairFailure.hint(401)
        val forbidden = PairFailure.hint(403)
        assertEquals("配对码无效或已过期，请在服务端重新生成", invalid)
        assertEquals("授权已失效，请重新扫码配对", revoked)
        assertEquals("本机未授权，请在服务端「移动端接入」加入本设备", forbidden)
        assertTrue(invalid != revoked && revoked != forbidden && invalid != forbidden)
    }

    @Test
    fun unreachableIsNotTheSameAsRejected() {
        assertEquals("服务端不可达，检查网络或隧道", PairFailure.hint(null))
        assertTrue(PairFailure.hint(500).contains("500"))
    }

    /** 隧道没起来不能报成「服务端不在线」。 */
    @Test
    fun tunnelDownHasItsOwnCopy() {
        assertEquals("隧道未连接，先建立隧道再配对", PairFailure.TUNNEL_DOWN)
        assertTrue(PairFailure.TUNNEL_DOWN != PairFailure.hint(null))
    }
}
