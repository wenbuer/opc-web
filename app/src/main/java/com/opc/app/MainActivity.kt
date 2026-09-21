package com.opc.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import com.opc.app.ui.nav.OpcApp
import com.opc.app.ui.theme.OpcTheme
import com.opc.app.ui.theme.ThemeMode

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val settingsStore = (application as OpcApplication).container.settingsStore
        setContent {
            // 先给跟随系统，DataStore 读出用户选择后立即覆盖：闪一帧也不会停在错误配色上
            val mode by settingsStore.themeMode.collectAsState(initial = ThemeMode.SYSTEM)
            OpcTheme(mode = mode) {
                OpcApp()
            }
        }
    }
}
