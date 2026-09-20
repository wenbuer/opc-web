package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.opc.app.ui.theme.OpcGreen

/**
 * 签名: CapsuleChip(text: String, selected: Boolean = false, onClick: () -> Unit = {}, hot: Boolean = false, modifier: Modifier = Modifier)
 *
 * 胶囊筛选芯片（可点）。selected = 金色容器底 + 金字；hot = 红色（待办/风险强调）；默认透明底 + 描边。
 */
@Composable
fun CapsuleChip(
    text: String,
    selected: Boolean = false,
    onClick: () -> Unit = {},
    hot: Boolean = false,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val background = when {
        selected -> scheme.primaryContainer
        hot -> scheme.errorContainer
        else -> Color.Transparent
    }
    val foreground = when {
        selected -> scheme.primary
        hot -> scheme.error
        else -> scheme.onSurface
    }
    val border = if (selected || hot) Modifier else Modifier.border(1.dp, scheme.outline, CircleShape)

    Row(
        modifier = modifier
            .height(32.dp)
            .clip(CircleShape)
            .background(background)
            .then(border)
            .clickable(onClick = onClick)
            .padding(horizontal = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text, style = MaterialTheme.typography.bodySmall, color = foreground, maxLines = 1)
    }
}

/**
 * 签名: GhostChip(text: String, modifier: Modifier = Modifier, leadingDot: Boolean = false, showChevron: Boolean = false)
 *
 * 只读小芯片（不可点）：容器底 + 暗字。用于「已连接 192.168.1.20」「未读 4」「按等待排序」。
 */
@Composable
fun GhostChip(
    text: String,
    modifier: Modifier = Modifier,
    leadingDot: Boolean = false,
    showChevron: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = modifier
            .height(26.dp)
            .clip(CircleShape)
            .background(scheme.surfaceContainerHigh)
            .padding(horizontal = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (leadingDot) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(OpcGreen))
        }
        Text(text, style = MaterialTheme.typography.labelMedium, color = scheme.onSurfaceVariant, maxLines = 1)
        if (showChevron) {
            Icon(
                imageVector = Icons.Default.KeyboardArrowDown,
                contentDescription = null,
                tint = scheme.onSurfaceVariant,
                modifier = Modifier.size(12.dp),
            )
        }
    }
}
