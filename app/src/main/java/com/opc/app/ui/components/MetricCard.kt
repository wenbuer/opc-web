package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/** 指标口径：NEUTRAL 中性 / ALERT 红（待裁决、风险）/ GOLD 金（在跑、主数字）。 */
enum class MetricTone { NEUTRAL, ALERT, GOLD }

/**
 * 签名: MetricCard(value: String, label: String, tone: MetricTone = MetricTone.NEUTRAL, modifier: Modifier = Modifier)
 *
 * 单张三指标卡。三张一排时由调用方摆 Row，每张 Modifier.weight(1f)，间隔 OpcSpacing.s。
 */
@Composable
fun MetricCard(
    value: String,
    label: String,
    tone: MetricTone = MetricTone.NEUTRAL,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val background = when (tone) {
        MetricTone.ALERT -> scheme.errorContainer
        MetricTone.GOLD -> scheme.primaryContainer
        MetricTone.NEUTRAL -> scheme.surfaceContainerHigh
    }
    val foreground = when (tone) {
        MetricTone.ALERT -> scheme.error
        MetricTone.GOLD -> scheme.primary
        MetricTone.NEUTRAL -> scheme.onSurface
    }

    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(background)
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(
            text = value,
            style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold),
            color = foreground,
            maxLines = 1,
        )
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = scheme.onSurfaceVariant,
            maxLines = 1,
        )
    }
}
