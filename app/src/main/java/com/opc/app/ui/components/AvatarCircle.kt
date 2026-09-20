package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * 签名: AvatarCircle(text: String, tone: TierTone = TierTone.RX, size: Dp = 38.dp, modifier: Modifier = Modifier)
 *
 * 首字母/角色码圆（无图片）：R0 红实底、R1 金实底、RX 靛容器底带描边、OK 绿实底、NEUTRAL 中性容器底。
 * 字号随 size 缩放（size * 0.34）。
 */
@Composable
fun AvatarCircle(
    text: String,
    tone: TierTone = TierTone.RX,
    size: Dp = 38.dp,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val background = when (tone) {
        TierTone.R0 -> scheme.error
        TierTone.R1 -> scheme.primary
        TierTone.RX -> scheme.secondaryContainer
        TierTone.OK -> scheme.tertiary
        TierTone.NEUTRAL -> scheme.surfaceContainerHigh
    }
    val foreground = when (tone) {
        TierTone.R0 -> scheme.onError
        TierTone.R1 -> scheme.onPrimary
        TierTone.RX -> scheme.secondary
        TierTone.OK -> scheme.onTertiary
        TierTone.NEUTRAL -> scheme.onSurfaceVariant
    }
    val outline = if (tone == TierTone.RX) Modifier.border(1.dp, scheme.outline, CircleShape) else Modifier

    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(background)
            .then(outline),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium.copy(
                fontSize = (size.value * 0.34f).sp,
                fontWeight = FontWeight.SemiBold,
            ),
            color = foreground,
            maxLines = 1,
        )
    }
}
