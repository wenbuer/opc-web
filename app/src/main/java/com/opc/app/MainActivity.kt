package com.opc.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.opc.app.ui.nav.OpcApp
import com.opc.app.ui.theme.OpcTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            // 跟随系统：亮色是银白科技，暗色回原战情室配色
            OpcTheme {
                OpcApp()
            }
        }
    }
}
