package com.opc.app.ui.theme

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** 纯 Kotlin，不碰 Android 框架：主题映射错了只会在真机上「点了没反应」，这里先钉住。 */
class ThemeModeTest {

    @Test
    fun darkAndLightIgnoreSystemSetting() {
        assertTrue(resolveDark(ThemeMode.DARK, systemInDark = false))
        assertTrue(resolveDark(ThemeMode.DARK, systemInDark = true))
        assertFalse(resolveDark(ThemeMode.LIGHT, systemInDark = false))
        assertFalse(resolveDark(ThemeMode.LIGHT, systemInDark = true))
    }

    @Test
    fun systemModeFollowsSystemSetting() {
        assertTrue(resolveDark(ThemeMode.SYSTEM, systemInDark = true))
        assertFalse(resolveDark(ThemeMode.SYSTEM, systemInDark = false))
    }

    /** 读写要闭环：存进去的 key 必须能解回同一个模式。 */
    @Test
    fun keyRoundTripsAndUnknownFallsBackToSystem() {
        ThemeMode.entries.forEach { mode ->
            assertEquals(mode, ThemeMode.fromKey(mode.key))
        }
        assertEquals(ThemeMode.SYSTEM, ThemeMode.fromKey(null))
        assertEquals(ThemeMode.SYSTEM, ThemeMode.fromKey("sepia"))
    }

    @Test
    fun labelsAreChineseForTheChipRow() {
        assertEquals("跟随系统", ThemeMode.SYSTEM.label)
        assertEquals("浅色", ThemeMode.LIGHT.label)
        assertEquals("深色", ThemeMode.DARK.label)
    }
}
