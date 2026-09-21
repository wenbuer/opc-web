package com.opc.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.unit.dp

/*
 * 品牌与语义色。种子仍是 opc-web 的金，但不同模式取不同深浅：
 *   金 = 决策 / 主操作，靛 = 角色 / 产出，红 = 待裁决 / 风险，绿 = 完成。
 *
 * 这五个名字是「跟随主题」的取值（不是常量）：浅色方案下要压暗才够对比度，
 * 暗色方案下用亮色。组件里直接用 OpcGold / OpcRed 就不会在浅色底上糊成一片。
 */
internal val OpcGold: Color
    @Composable get() = MaterialTheme.colorScheme.primary

internal val OpcIndigo: Color
    @Composable get() = MaterialTheme.colorScheme.secondary

internal val OpcRed: Color
    @Composable get() = MaterialTheme.colorScheme.error

internal val OpcGreen: Color
    @Composable get() = MaterialTheme.colorScheme.tertiary

/* ============ 银白科技（浅色，默认） ============
 * 冷灰蓝打底，靠 surfaceContainer 五档拉开层级，不用阴影。
 * 金属感只给结构件（卡片、导航栏、按钮），其余保持克制。
 */

internal val SilverBackground = Color(0xFFEDF1F6)
internal val SilverBackgroundDeep = Color(0xFFE2E8F1)
internal val SilverSurface = Color(0xFFFAFBFD)
internal val SilverSurfaceLow = Color(0xFFF2F5F9)
internal val SilverSurfaceHigh = Color(0xFFE7ECF3)
internal val SilverSurfaceHighest = Color(0xFFDCE3EC)
internal val SilverCardTop = Color(0xFFFFFFFF)
internal val SilverCardBottom = Color(0xFFF3F6FA)
internal val SilverText = Color(0xFF151A22)
internal val SilverDim = Color(0xFF5A6472)

// 金压在 8A6420：银白底上对比度 5.17（AA 正常文本），实底配白字 5.35；
// 也是 opc-web 浅色主题的金，一套品牌色不用两处维护。
internal val SilverGold = Color(0xFF8A6420)
internal val SilverGoldContainer = Color(0xFFF7EBCB)
internal val SilverIndigo = Color(0xFF3E5FA8)
internal val SilverIndigoContainer = Color(0xFFE4EAF8)
internal val SilverRed = Color(0xFFB3261E)
internal val SilverRedContainer = Color(0xFFFBE9E7)
internal val SilverGreen = Color(0xFF1F7A5A)
internal val SilverGreenContainer = Color(0xFFE1F2EA)

internal val SilverOutline = Color(0xFFB4BFCD)
internal val SilverOutlineVariant = Color(0xFFD5DDE7)

/* ============ 暗色（跟随系统） ============ */

internal val DarkBackground = Color(0xFF0E1117)
internal val DarkSurface = Color(0xFF161A21)
internal val DarkSurfaceLow = Color(0xFF1B1F27)
internal val DarkSurfaceHigh = Color(0xFF252932)
internal val DarkSurfaceHighest = Color(0xFF2B2F39)
internal val DarkText = Color(0xFFE8E4DC)
internal val DarkDim = Color(0xFFA8A49C)

internal val DarkGold = Color(0xFFE8B73D)
internal val DarkGoldContainer = Color(0xFF3A2F12)
internal val DarkIndigo = Color(0xFF9DB4F0)
internal val DarkIndigoContainer = Color(0xFF1E2748)
internal val DarkRed = Color(0xFFFF8A80)
internal val DarkRedContainer = Color(0xFF3A1A17)
internal val DarkGreen = Color(0xFF79D6AB)
internal val DarkGreenContainer = Color(0xFF12301F)

/* 实底色上的前景 */
internal val OnGoldLight = Color(0xFFFFFFFF)
internal val OnGoldDark = Color(0xFF2A1F05)
internal val OnAccentLight = Color(0xFFFFFFFF)
internal val OnAccentDark = Color(0xFF0B1330)

/* ============ 科技感底纹：冷色网格 + 顶部微光 ============ */

/** 页面底：银白纵向渐变，顶部偏冷白、底部压一档灰蓝，像金属受光面。 */
@Composable
internal fun silverBackgroundBrush(): Brush {
    val scheme = MaterialTheme.colorScheme
    return Brush.verticalGradient(
        listOf(scheme.surface, scheme.background, scheme.surfaceContainerHigh),
    )
}

/**
 * 细网格底纹。只在背景层用，线宽 1px、透明度很低，
 * 拉近看是工程图纸的感觉，远看只是一层灰。
 */
internal fun Modifier.techGrid(
    cell: androidx.compose.ui.unit.Dp = 26.dp,
    alpha: Float = 0.05f,
): Modifier = drawBehind {
    val step = cell.toPx()
    if (step <= 0f) return@drawBehind
    val line = Color(0xFF2C4A78).copy(alpha = alpha)
    var x = 0f
    while (x <= size.width) {
        drawLine(line, Offset(x, 0f), Offset(x, size.height), strokeWidth = 1f)
        x += step
    }
    var y = 0f
    while (y <= size.height) {
        drawLine(line, Offset(0f, y), Offset(size.width, y), strokeWidth = 1f)
        y += step
    }
}
