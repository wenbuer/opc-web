package com.opc.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * 签名: SectionHeader(title: String, meta: String? = null, action: String? = null, onAction: (() -> Unit)? = null, modifier: Modifier = Modifier)
 *
 * 小节标题：标题 13sp/600 + 等宽 meta（如 "4 ROLES"）+ 右侧等宽 action（靛蓝，onAction 非空时可点）。
 * 自带上下外边距（top 22dp / bottom 10dp），调用方不用再加。
 */
@Composable
fun SectionHeader(
    title: String,
    meta: String? = null,
    action: String? = null,
    onAction: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme

    Row(
        modifier = modifier.fillMaxWidth().padding(top = 22.dp, bottom = 10.dp),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            color = scheme.onSurface,
            modifier = Modifier.alignByBaseline(),
        )
        if (meta != null) {
            Text(
                text = meta,
                style = MaterialTheme.typography.labelMedium,
                color = scheme.onSurfaceVariant,
                modifier = Modifier.alignByBaseline().padding(start = 8.dp),
            )
        }
        Spacer(Modifier.weight(1f))
        if (action != null) {
            Text(
                text = action,
                style = MaterialTheme.typography.labelMedium,
                color = scheme.secondary,
                modifier = Modifier
                    .alignByBaseline()
                    .then(if (onAction != null) Modifier.clickable { onAction() } else Modifier),
            )
        }
    }
}
