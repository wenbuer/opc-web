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
            OpcTheme(darkTheme = true) {
                OpcApp()
            }
        }
    }
}
