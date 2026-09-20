package com.opc.app.ui.theme

import androidx.compose.ui.graphics.Color

/*
 * SPEC §2 视觉 token。种子色 = opc-web 的金 #E8B73D。
 * 语义：金 = 决策/主操作，靛 = 角色/产出，红 = 待裁决/风险，绿 = 完成。
 */

val OpcGold = Color(0xFFE8B73D)
val OpcGoldContainer = Color(0xFF3A2F12)

val OpcIndigo = Color(0xFF4C6EF5)
val OpcIndigoContainer = Color(0xFF1E2748)

val OpcRed = Color(0xFFE74C3C)
val OpcRedContainer = Color(0xFF3A1A17)

val OpcGreen = Color(0xFF35B97C)
val OpcGreenContainer = Color(0xFF12301F)

val OpcDarkBackground = Color(0xFF0E1117)
val OpcDarkSurface = Color(0xFF161A21)
val OpcDarkSurfaceLow = Color(0xFF1B1F27)
val OpcDarkSurfaceHigh = Color(0xFF252932)
val OpcDarkSurfaceHighest = Color(0xFF2B2F39)
val OpcDarkText = Color(0xFFE8E4DC)
val OpcDarkDim = Color(0xFFA8A49C)

/* ---- 浅色方案专用（对齐 design/index.html 的 light token，不属对外契约） ---- */

internal val OpcLightBackground = Color(0xFFF7F4EE)
internal val OpcLightSurface = Color(0xFFFFFDF8)
internal val OpcLightSurfaceLow = Color(0xFFF6F2EA)
internal val OpcLightSurfaceHigh = Color(0xFFEAE5DC)
internal val OpcLightSurfaceHighest = Color(0xFFE3DED4)
internal val OpcLightGold = Color(0xFF8A6420)
internal val OpcLightGoldContainer = Color(0xFFF2E9D4)
internal val OpcLightIndigo = Color(0xFF3D5A9E)
internal val OpcLightIndigoContainer = Color(0xFFE4E9F6)
internal val OpcLightRed = Color(0xFFB3261E)
internal val OpcLightRedContainer = Color(0xFFFBE9E7)
internal val OpcLightGreen = Color(0xFF2F7D5C)
internal val OpcLightGreenContainer = Color(0xFFE2F3EA)

/* on-X 伴随色：金/靛/红/绿实底上的前景 */
internal val OpcOnGold = Color(0xFF2A1F05)
internal val OpcOnIndigo = Color(0xFF0B1330)
internal val OpcOnRed = Color(0xFF3A0D0A)
internal val OpcOnGreen = Color(0xFF04281A)
internal val OpcGoldSoft = Color(0xFF9DB4F0)
internal val OpcRedSoft = Color(0xFFFF8A80)
internal val OpcGreenSoft = Color(0xFF79D6AB)
