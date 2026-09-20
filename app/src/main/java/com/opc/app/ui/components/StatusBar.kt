package com.opc.app.ui.components

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
 * 不要各自再写 statusBarsPadding()，否则和本组件叠加会把标题压下去。
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
 * 用 asPaddingValues 而不是 windowInsetsPadding：后者需要在组合作用域里调用，
 * 会把调用方也绑成 @Composable，没必要。
 */
@Composable
fun Modifier.statusBarPadding(extra: Dp = 0.dp): Modifier {
    val inset = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    return this.padding(top = inset + extra)
}
