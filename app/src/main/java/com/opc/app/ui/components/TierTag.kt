package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp

/** 等级色：R0 人（你）/ R1 老板助理 / RX 执行角色 / OK 完成 / NEUTRAL 中性。 */
enum class TierTone { R0, R1, RX, OK, NEUTRAL }

/**
 * 签名: TierTag(text: String, tone: TierTone = TierTone.NEUTRAL, modifier: Modifier = Modifier)
 *
 * 等级色小标签（等宽字）：R0 红 / R1 金 / RX 靛 / OK 绿 / NEUTRAL 中性容器色。
 */
@Composable
fun TierTag(text: String, tone: TierTone = TierTone.NEUTRAL, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    val background = when (tone) {
        TierTone.R0 -> scheme.errorContainer
        TierTone.R1 -> scheme.primaryContainer
        TierTone.RX -> scheme.secondaryContainer
        TierTone.OK -> scheme.tertiaryContainer
        TierTone.NEUTRAL -> scheme.surfaceContainerHighest
    }
    val foreground = when (tone) {
        TierTone.R0 -> scheme.error
        TierTone.R1 -> scheme.primary
        TierTone.RX -> scheme.secondary
        TierTone.OK -> scheme.tertiary
        TierTone.NEUTRAL -> scheme.onSurfaceVariant
    }

    Box(
        modifier = modifier
            .height(22.dp)
            .clip(CircleShape)
            .background(background)
            .padding(horizontal = 9.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = MaterialTheme.typography.labelMedium, color = foreground, maxLines = 1)
    }
}
