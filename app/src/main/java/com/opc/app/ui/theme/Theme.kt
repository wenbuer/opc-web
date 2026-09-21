package com.opc.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/*
 * 银白科技（浅色）为默认，暗色跟随系统。
 * 层级一律用 surfaceContainer 五档，不用阴影；金属感留给结构件（卡片、底栏、按钮）。
 */

/** 银白科技：冷灰蓝底 + 近白卡片 + 象牙金主色。 */
val OpcSilverColors = lightColorScheme(
    primary = SilverGold,
    onPrimary = OnGoldLight,
    primaryContainer = SilverGoldContainer,
    onPrimaryContainer = SilverGold,

    secondary = SilverIndigo,
    onSecondary = OnAccentLight,
    secondaryContainer = SilverIndigoContainer,
    onSecondaryContainer = SilverIndigo,

    tertiary = SilverGreen,
    onTertiary = OnAccentLight,
    tertiaryContainer = SilverGreenContainer,
    onTertiaryContainer = SilverGreen,

    error = SilverRed,
    onError = OnAccentLight,
    errorContainer = SilverRedContainer,
    onErrorContainer = SilverRed,

    background = SilverBackground,
    onBackground = SilverText,
    surface = SilverSurface,
    onSurface = SilverText,
    surfaceVariant = SilverSurfaceLow,
    onSurfaceVariant = SilverDim,
    surfaceTint = SilverGold,

    surfaceContainerLowest = SilverCardTop,
    surfaceContainerLow = SilverSurfaceLow,
    surfaceContainer = SilverSurface,
    surfaceContainerHigh = SilverSurfaceHigh,
    surfaceContainerHighest = SilverSurfaceHighest,

    outline = SilverOutline,
    outlineVariant = SilverOutlineVariant,
    inverseSurface = Color(0xFF232A35),
    inverseOnSurface = SilverSurface,
    scrim = Color(0x66131A24),
)

/** 暗色：原战情室配色，跟随系统时才启用。 */
val OpcDarkColors = darkColorScheme(
    primary = DarkGold,
    onPrimary = OnGoldDark,
    primaryContainer = DarkGoldContainer,
    onPrimaryContainer = DarkGold,

    secondary = DarkIndigo,
    onSecondary = OnAccentDark,
    secondaryContainer = DarkIndigoContainer,
    onSecondaryContainer = DarkIndigo,

    tertiary = DarkGreen,
    onTertiary = OnAccentDark,
    tertiaryContainer = DarkGreenContainer,
    onTertiaryContainer = DarkGreen,

    error = DarkRed,
    onError = OnAccentDark,
    errorContainer = DarkRedContainer,
    onErrorContainer = DarkRed,

    background = DarkBackground,
    onBackground = DarkText,
    surface = DarkSurface,
    onSurface = DarkText,
    surfaceVariant = DarkSurfaceLow,
    onSurfaceVariant = DarkDim,
    surfaceTint = DarkGold,

    surfaceContainerLowest = DarkBackground,
    surfaceContainerLow = DarkSurfaceLow,
    surfaceContainer = DarkSurface,
    surfaceContainerHigh = DarkSurfaceHigh,
    surfaceContainerHighest = DarkSurfaceHighest,

    outline = Color(0x21E0DCD2),
    outlineVariant = Color(0x12E0DCD2),
    inverseSurface = DarkText,
    inverseOnSurface = DarkBackground,
    scrim = Color(0xE6000000),
)

/**
 * 签名: OpcTheme(darkTheme: Boolean = isSystemInDarkTheme(), content)
 *
 * 默认跟随系统：亮色下是银白科技，暗色下回到原战情室配色。
 * 真机在系统设置里切深浅即可，不用改代码。
 * 这个签名保留给预览与单屏渲染用；App 实际走下面的 mode 重载。
 */
@Composable
fun OpcTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) OpcDarkColors else OpcSilverColors,
        typography = OpcTypography,
        shapes = OpcShapes,
        content = content,
    )
}

/**
 * 签名: OpcTheme(mode: ThemeMode, content)
 *
 * 用户选的模式优先于系统：DARK 恒暗、LIGHT 恒亮、SYSTEM 才看系统设置。
 * 模式在 MainActivity 里从 DataStore 读出来，改一次全树重组。
 */
@Composable
fun OpcTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    OpcTheme(darkTheme = resolveDark(mode, isSystemInDarkTheme()), content = content)
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
