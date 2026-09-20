package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.opc.app.ui.theme.OpcGold
import com.opc.app.ui.theme.OpcIndigo

/** 默认 7 天标签：一 二 三 四 五 今 日。 */
val SparkBarLabels: List<String> = listOf("一", "二", "三", "四", "五", "今", "日")

/**
 * 签名: SparkBars(values: List<Double>, highlightLast: Boolean = true, labels: List<String> = SparkBarLabels, height: Dp = 112.dp, modifier: Modifier = Modifier)
 *
 * 纯 Compose 柱形图（无图表库）：柱高 = value / max，最低保留 4% 以免归零消失；
 * highlightLast = true 时最后一根用靛蓝，其余用金。values.size 与 labels.size 不必相等（按序取标签）。
 */
@Composable
fun SparkBars(
    values: List<Double>,
    highlightLast: Boolean = true,
    labels: List<String> = SparkBarLabels,
    height: Dp = 112.dp,
    modifier: Modifier = Modifier,
) {
    val max = values.maxOrNull() ?: 0.0
    val barArea = height - 22.dp

    Row(
        modifier = modifier.fillMaxWidth().height(height),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        values.forEachIndexed { index, value ->
            val fraction = if (max <= 0.0) 0.04f else (value / max).toFloat().coerceIn(0.04f, 1f)
            val barColor = if (highlightLast && index == values.lastIndex) OpcIndigo else OpcGold

            Column(
                modifier = Modifier.weight(1f).fillMaxHeight(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Bottom,
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(barArea * fraction)
                        .clip(RoundedCornerShape(topStart = 7.dp, topEnd = 7.dp, bottomStart = 4.dp, bottomEnd = 4.dp))
                        .background(Brush.verticalGradient(listOf(barColor, barColor.copy(alpha = 0.45f)))),
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    text = labels.getOrElse(index) { "" },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        }
    }
}
