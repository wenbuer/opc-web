package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/**
 * 签名: SubTaskCard(no: String, title: String, role: String, expect: String, stateText: String, stateTone: TierTone = TierTone.NEUTRAL, trailingText: String? = null, modifier: Modifier = Modifier)
 *
 * 群聊里的结构化子任务卡：左侧 3dp 等级色边（随 stateTone，OK = 绿）+ 编号(等宽) + 标题 + 角色标签，
 * 正文是期望产出，脚注是状态标签 + 等宽时间（trailingText）。
 */
@Composable
fun SubTaskCard(
    no: String,
    title: String,
    role: String,
    expect: String,
    stateText: String,
    stateTone: TierTone = TierTone.NEUTRAL,
    trailingText: String? = null,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val edgeColor = when (stateTone) {
        TierTone.OK -> scheme.tertiary
        TierTone.R0 -> scheme.error
        TierTone.RX -> scheme.secondary
        TierTone.R1 -> scheme.primary
        TierTone.NEUTRAL -> scheme.primary
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(topStart = 0.dp, topEnd = 16.dp, bottomEnd = 16.dp, bottomStart = 0.dp))
            .background(scheme.surfaceContainerLow)
            .drawBehind {
                drawRect(color = edgeColor, size = Size(3.dp.toPx(), size.height))
            }
            .padding(horizontal = 13.dp, vertical = 12.dp),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(no, style = MaterialTheme.typography.labelMedium, color = scheme.primary, maxLines = 1)
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                color = scheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            TierTag(text = role, tone = TierTone.RX)
        }

        Text(
            text = expect,
            style = MaterialTheme.typography.bodySmall,
            color = scheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 6.dp),
        )

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(top = 9.dp),
        ) {
            TierTag(text = stateText, tone = stateTone)
            if (trailingText != null) {
                Text(trailingText, style = MaterialTheme.typography.labelMedium, color = scheme.secondary, maxLines = 1)
            }
        }
    }
}
