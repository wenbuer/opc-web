package com.opc.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp

/**
 * 签名: Bubble(text: String, time: String, mine: Boolean = false, who: String? = null, avatarText: String? = null, avatarTone: TierTone = if (mine) TierTone.R1 else TierTone.RX, modifier: Modifier = Modifier)
 *
 * 聊天气泡。mine = true 走金色底（右下角收窄），对方走容器底（左下角收窄）。
 * who != null 时渲染「谁 + 等宽时间」头行（mine 时时间在左）；avatarText != null 时在气泡外侧画首字母圆。
 */
@Composable
fun Bubble(
    text: String,
    time: String,
    mine: Boolean = false,
    who: String? = null,
    avatarText: String? = null,
    avatarTone: TierTone = if (mine) TierTone.R1 else TierTone.RX,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val bubbleShape = RoundedCornerShape(
        topStart = 18.dp,
        topEnd = 18.dp,
        bottomStart = if (mine) 18.dp else 6.dp,
        bottomEnd = if (mine) 6.dp else 18.dp,
    )
    val bubbleColor = if (mine) scheme.primary else scheme.surfaceContainerLow
    val contentColor = if (mine) scheme.onPrimary else scheme.onSurface

    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        if (avatarText != null && !mine) {
            AvatarCircle(text = avatarText, tone = avatarTone, size = 30.dp)
        }

        Column(
            modifier = Modifier.weight(1f, fill = false),
            horizontalAlignment = if (mine) Alignment.End else Alignment.Start,
        ) {
            if (who != null) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(7.dp),
                ) {
                    if (mine) {
                        Text(time, style = MaterialTheme.typography.labelSmall, color = scheme.onSurfaceVariant, maxLines = 1)
                        Text(who, style = MaterialTheme.typography.titleSmall, color = scheme.onSurface, maxLines = 1)
                    } else {
                        Text(who, style = MaterialTheme.typography.titleSmall, color = scheme.onSurface, maxLines = 1)
                        Text(time, style = MaterialTheme.typography.labelSmall, color = scheme.onSurfaceVariant, maxLines = 1)
                    }
                }
                Spacer(Modifier.height(5.dp))
            }

            Box(
                modifier = Modifier
                    .clip(bubbleShape)
                    .background(bubbleColor)
                    .padding(horizontal = 14.dp, vertical = 11.dp),
            ) {
                Text(text = text, style = MaterialTheme.typography.bodyMedium, color = contentColor)
            }
        }

        if (avatarText != null && mine) {
            AvatarCircle(text = avatarText, tone = avatarTone, size = 30.dp)
        }
    }
}
