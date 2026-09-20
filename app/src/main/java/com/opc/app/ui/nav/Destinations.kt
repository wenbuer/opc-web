package com.opc.app.ui.nav

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Send
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * 底栏五项。连接页不在底栏：未配对时它是唯一的前台，配对后不再出现，
 * 所以它只有 route 常量（CONNECT_ROUTE）没有条目。
 */
enum class OpcDestination(val route: String, val label: String, val icon: ImageVector) {
    OVERVIEW("overview", "总览", Icons.Default.Home),
    WORKBENCH("workbench", "工作台", Icons.Default.Send),
    REVIEW("review", "批阅台", Icons.Default.CheckCircle),
    MESSAGES("messages", "消息", Icons.Default.Email),
    PROFILE("profile", "我的", Icons.Default.Person),
}

const val CONNECT_ROUTE = "connect"
