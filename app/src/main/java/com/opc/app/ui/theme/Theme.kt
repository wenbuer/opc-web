package com.opc.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/* SPEC §2：暗色为默认，浅色可用。surfaceContainer 五档做层级，不用阴影。 */

val OpcDarkColors = darkColorScheme(
    primary = OpcGold,
    onPrimary = OpcOnGold,
    primaryContainer = OpcGoldContainer,
    onPrimaryContainer = OpcGold,

    secondary = OpcIndigo,
    onSecondary = OpcOnIndigo,
    secondaryContainer = OpcIndigoContainer,
    onSecondaryContainer = OpcGoldSoft,

    tertiary = OpcGreen,
    onTertiary = OpcOnGreen,
    tertiaryContainer = OpcGreenContainer,
    onTertiaryContainer = OpcGreenSoft,

    error = OpcRed,
    onError = OpcOnRed,
    errorContainer = OpcRedContainer,
    onErrorContainer = OpcRedSoft,

    background = OpcDarkBackground,
    onBackground = OpcDarkText,
    surface = OpcDarkSurface,
    onSurface = OpcDarkText,
    surfaceVariant = OpcDarkSurfaceLow,
    onSurfaceVariant = OpcDarkDim,
    surfaceTint = OpcGold,

    surfaceContainerLowest = OpcDarkBackground,
    surfaceContainerLow = OpcDarkSurfaceLow,
    surfaceContainer = OpcDarkSurface,
    surfaceContainerHigh = OpcDarkSurfaceHigh,
    surfaceContainerHighest = OpcDarkSurfaceHighest,

    outline = Color(0x21E0DCD2),
    outlineVariant = Color(0x12E0DCD2),
    inverseSurface = OpcDarkText,
    inverseOnSurface = OpcDarkBackground,
    scrim = Color(0xE6000000),
)

val OpcLightColors = lightColorScheme(
    primary = OpcLightGold,
    onPrimary = Color.White,
    primaryContainer = OpcLightGoldContainer,
    onPrimaryContainer = OpcLightGold,

    secondary = OpcLightIndigo,
    onSecondary = Color.White,
    secondaryContainer = OpcLightIndigoContainer,
    onSecondaryContainer = OpcLightIndigo,

    tertiary = OpcLightGreen,
    onTertiary = Color.White,
    tertiaryContainer = OpcLightGreenContainer,
    onTertiaryContainer = OpcLightGreen,

    error = OpcLightRed,
    onError = Color.White,
    errorContainer = OpcLightRedContainer,
    onErrorContainer = OpcLightRed,

    background = OpcLightBackground,
    onBackground = Color(0xFF1B1C1A),
    surface = OpcLightSurface,
    onSurface = Color(0xFF1B1C1A),
    surfaceVariant = OpcLightSurfaceLow,
    onSurfaceVariant = Color(0xFF5B5F66),
    surfaceTint = OpcLightGold,

    surfaceContainerLowest = OpcLightSurface,
    surfaceContainerLow = OpcLightSurfaceLow,
    surfaceContainer = OpcLightSurfaceLow,
    surfaceContainerHigh = OpcLightSurfaceHigh,
    surfaceContainerHighest = OpcLightSurfaceHighest,

    outline = Color(0x1F1C1A14),
    outlineVariant = Color(0x121C1A14),
    inverseSurface = Color(0xFF2A2D33),
    inverseOnSurface = OpcLightBackground,
    scrim = Color(0x6B181612),
)

/** 签名: OpcTheme(darkTheme: Boolean = true, content: @Composable () -> Unit) —— 暗色为默认。 */
@Composable
fun OpcTheme(darkTheme: Boolean = true, content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) OpcDarkColors else OpcLightColors,
        typography = OpcTypography,
        shapes = OpcShapes,
        content = content,
    )
}

/** 间距刻度，避免页面里散落魔法数字。 */
object OpcSpacing {
    val xs = 4.dp
    val s = 8.dp
    val m = 12.dp
    val l = 16.dp
    val xl = 22.dp
    val xxl = 28.dp
}

/** 页面左右统一内边距。 */
val OpcScreenPadding: Dp = 16.dp
