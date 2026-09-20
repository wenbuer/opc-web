package com.opc.app.ui.components

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * 签名: StatusBarSpacer(extra: Dp = 0.dp)
 *
 * edge-to-edge 下顶部状态栏的统一占位。每个页面顶部（AppBar 之前）放一个即可，
 * 不要再各自写 statusBarsPadding()，否则会与 Scaffold 的内容内缩叠加出空白。
 * 根 Scaffold 的 contentWindowInsets 已清零，顶层就靠这一个组件吃状态栏。
 */
@Composable
fun StatusBarSpacer(extra: Dp = 0.dp) {
    val inset = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    Spacer(Modifier.fillMaxWidth().height(inset + extra))
}

/**
 * 签名: Modifier.statusBarPadding(extra: Dp = 0.dp)
 *
 * 给已有容器补顶部安全边距（比插一个 Spacer 少一层布局）。与 StatusBarSpacer 二选一。
 */
@Composable
fun Modifier.statusBarPadding(extra: Dp = 0.dp): Modifier {
    val inset = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    return this.padding(top = inset + extra)
}

/**
 * 签名: Modifier.imeBottomPadding()
 *
 * 键盘占位只补「键盘比系统导航栏高出来的那一段」。
 * 直接用 imePadding() 会把导航栏那几十 dp 再补一次 —— 底栏已经在让位，
 * 结果就是输入框和键盘之间多出一条空白。这里减掉导航栏高度，就不会重复。
 */
@Composable
fun Modifier.imeBottomPadding(): Modifier {
    val imeBottom = WindowInsets.ime.asPaddingValues().calculateBottomPadding()
    val navBottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    return this.padding(bottom = (imeBottom - navBottom).coerceAtLeast(0.dp))
}
