package com.opc.app.ui.theme

/**
 * 主题模式：设备偏好，与配对无关，解配对不清（见 SettingsStore.clearPairing）。
 * 三个值都要有中文 label —— 界面直接显示 label，不再各自写 when。
 */
enum class ThemeMode(val key: String, val label: String) {
    SYSTEM("system", "跟随系统"),
    LIGHT("light", "浅色"),
    DARK("dark", "深色");

    companion object {
        /** 持久化读回：认不出的字符串（老版本写入、手改 DataStore）一律退回跟随系统。 */
        fun fromKey(key: String?): ThemeMode = entries.firstOrNull { it.key == key } ?: SYSTEM
    }
}

/**
 * 纯映射：模式 + 系统深浅 -> 是否用暗色。
 * OpcTheme(mode) 与单测共用这一条，避免界面用一套、测试测另一套。
 */
fun resolveDark(mode: ThemeMode, systemInDark: Boolean): Boolean = when (mode) {
    ThemeMode.DARK -> true
    ThemeMode.LIGHT -> false
    ThemeMode.SYSTEM -> systemInDark
}
