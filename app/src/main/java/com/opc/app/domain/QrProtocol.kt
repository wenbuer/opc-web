package com.opc.app.domain

import android.graphics.Bitmap
import android.graphics.Color as AndroidColor
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import java.net.URLDecoder
import java.util.UUID

/**
 * 配对二维码协议（见 docs/pairing-protocol.md）：
 *   opc://pair?h=10.9.0.1&p=8901&c=K7QP-3M2X&wg=<base64url(conf)>&v=1.18.0
 * h 是「手机要访问的地址」：有隧道时是服务端隧道地址，没有隧道时是局域网地址。
 * 也接受 http(s):// 地址直接带参数的写法。
 */
data class PairTicket(
    val baseUrl: String,
    val code: String,
    val serverVersion: String?,
    /** 二维码里的隧道骨架；老二维码没有这一项，为 null 时照旧直连。 */
    val wire: WireConfig? = null,
)

object PairAddress {

    const val DEFAULT_PORT = 8901

    /**
     * 主机名允许不带点号（`pc-name` 也要能连），但必须是 ASCII 主机名字符集：
     * 中文、空格、URL 里的 userinfo 之类一律不是可达地址。
     */
    private val HOST_PATTERN = Regex("^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")

    /**
     * "192.168.1.20" / "pc-name:8901" / "http://x:8901/pair?c=1" 都归一成 http://host:port。
     * 只保留 origin：路径、查询、尾斜杠一律切掉，否则 Retrofit 的 baseUrl 会把路径带进每个请求。
     */
    fun normalize(raw: String): String? {
        val trimmed = raw.trim()
        if (trimmed.isEmpty()) return null
        val withoutScheme = trimmed.substringAfter("://", trimmed)
        val hostPort = withoutScheme.substringBefore('/').substringBefore('?').substringBefore('#')
        if (hostPort.isEmpty()) return null
        val host = hostPort.substringBefore(':')
        val port = hostPort.substringAfter(':', DEFAULT_PORT.toString())
        if (!HOST_PATTERN.matches(host)) return null
        if (port.toIntOrNull() == null) return null
        return "http://" + host + ":" + port
    }
}

object QrProtocol {

    fun parse(raw: String): PairTicket? {
        val text = raw.trim()
        if (text.isEmpty()) return null
        return when {
            text.startsWith("opc://pair", ignoreCase = true) -> fromQuery(parseQuery(text.substringAfter('?', "")))
            text.startsWith("http://", true) || text.startsWith("https://", true) -> {
                val base = PairAddress.normalize(text.substringBefore('?')) ?: return null
                val q = parseQuery(text.substringAfter('?', ""))
                val code = q["c"] ?: q["code"] ?: return null
                PairTicket(base, code, q["v"], wireOf(q))
            }
            else -> null
        }
    }

    /** 手动输入：地址 + 配对码。手填拿不到隧道参数，走直连。 */
    fun manual(address: String, code: String): PairTicket? {
        val base = PairAddress.normalize(address) ?: return null
        val c = code.trim().uppercase()
        if (c.isEmpty()) return null
        return PairTicket(base, c, null)
    }

    fun newDeviceCode(): String {
        val hex = UUID.randomUUID().toString().replace("-", "").uppercase()
        return "DEV-" + hex.substring(0, 4) + "-" + hex.substring(4, 8)
    }

    private fun fromQuery(q: Map<String, String>): PairTicket? {
        val host = q["h"] ?: return null
        val port = q["p"] ?: PairAddress.DEFAULT_PORT.toString()
        val code = q["c"] ?: q["code"] ?: return null
        if (PairAddress.normalize(host) == null) return null
        return PairTicket("http://$host:$port", code, q["v"], wireOf(q))
    }

    /**
     * wg 优先（整份 conf），逐字段兜底。两种情况都坏掉就返回 null —— 只丢隧道，
     * 不影响配对本身（老二维码必须照样能配上）。
     */
    private fun wireOf(q: Map<String, String>): WireConfig? {
        q["wg"]?.let { encoded -> WireConf.parseEncoded(encoded)?.let { return it } }
        val fields = WireConfig(
            publicKey = q["wg_pub"]?.takeIf { it.isNotBlank() },
            endpoint = q["wg_ep"]?.takeIf { it.isNotBlank() },
            address = q["wg_ip"]?.takeIf { it.isNotBlank() },
            dns = q["wg_dns"]?.takeIf { it.isNotBlank() },
            allowedIps = q["wg_allowed"]?.takeIf { it.isNotBlank() },
            mtu = q["wg_mtu"]?.trim()?.toIntOrNull(),
        )
        return fields.takeUnless { it.isEmpty }
    }

    private fun parseQuery(query: String): Map<String, String> =
        query.split('&')
            .mapNotNull { part ->
                if (part.isBlank() || !part.contains('=')) return@mapNotNull null
                val k = part.substringBefore('=').lowercase()
                val v = runCatching { URLDecoder.decode(part.substringAfter('='), "UTF-8") }
                    .getOrDefault(part.substringAfter('='))
                k to v
            }
            .toMap()
}

/** 生成配对二维码位图（服务端未就绪时，手机端也能演示配对流程）。 */
object QrBitmap {
    fun encode(content: String, sizePx: Int = 640): Bitmap {
        val hints = mapOf(
            EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
            EncodeHintType.MARGIN to 1,
            EncodeHintType.CHARACTER_SET to "UTF-8",
        )
        val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, sizePx, sizePx, hints)
        val pixels = IntArray(sizePx * sizePx)
        for (y in 0 until sizePx) {
            for (x in 0 until sizePx) {
                pixels[y * sizePx + x] = if (matrix[x, y]) AndroidColor.BLACK else AndroidColor.WHITE
            }
        }
        return Bitmap.createBitmap(pixels, sizePx, sizePx, Bitmap.Config.ARGB_8888)
    }
}
