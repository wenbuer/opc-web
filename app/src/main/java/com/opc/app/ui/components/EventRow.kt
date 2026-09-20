package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.opc.app.ui.theme.OpcGold
import com.opc.app.ui.theme.OpcGreen
import com.opc.app.ui.theme.OpcRed

/** 事件点颜色。domain 的 EventKind 由调用方映射：DONE -> DONE，ERROR -> ERROR，其余 -> INFO。 */
enum class EventTone { INFO, DONE, ERROR }

/**
 * 签名: EventRow(time: String, text: String, tone: EventTone = EventTone.INFO, modifier: Modifier = Modifier)
 *
 * 左侧圆点 + 等宽时间 + 正文。左对齐竖线由调用方容器加（design 里的 .rowlist）。
 */
@Composable
fun EventRow(
    time: String,
    text: String,
    tone: EventTone = EventTone.INFO,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val dotColor = when (tone) {
        EventTone.INFO -> OpcGold
        EventTone.DONE -> OpcGreen
        EventTone.ERROR -> OpcRed
    }

    Row(
        modifier = modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Box(
            Modifier
                .padding(top = 6.dp)
                .size(7.dp)
                .clip(CircleShape)
                .background(dotColor),
        )
        Text(
            text = time,
            style = MaterialTheme.typography.labelSmall,
            color = scheme.onSurfaceVariant,
            maxLines = 1,
        )
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            color = scheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
    }
}
