package com.opc.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.opc.app.data.LinkState
import com.opc.app.domain.EventKind
import com.opc.app.domain.RoleState
import com.opc.app.ui.components.EventTone
import com.opc.app.ui.components.StatusBarSpacer
import com.opc.app.ui.components.TierTag
import com.opc.app.ui.components.TierTone
import com.opc.app.ui.theme.CardRadius
import com.opc.app.ui.theme.OpcGold
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/*
 * SPEC 的组件清单没覆盖到页头、小节标题、设置行这些，收在这一份里：五个屏共用。
 * 已经在 ui/components 落地的（CapsuleChip / TierTag / MetricCard / HeroCard / SparkBars /
 * EventRow / AvatarCircle）一律直接用，不重复造。
 */

/** 屏幕内统一的页头：状态栏占位 + 标题 + 右侧动作。 */
@Composable
internal fun LocalTopBar(
    title: String,
    subtitle: String? = null,
    actions: @Composable RowScope.() -> Unit = {},
) {
    Column(Modifier.fillMaxWidth()) {
        StatusBarSpacer()
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.s),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
                if (subtitle != null) {
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            actions()
        }
    }
}

/** 小节标题：左标题 + 等宽元信息 + 右侧动作文字。 */
@Composable
internal fun LocalSectionHeader(
    title: String,
    meta: String? = null,
    action: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = OpcSpacing.l, bottom = OpcSpacing.m),
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
        if (meta != null) {
            Text(
                meta,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = OpcSpacing.s),
            )
        }
        Spacer(Modifier.weight(1f))
        if (action != null) {
            Text(
                action,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
                modifier = if (onAction != null) Modifier.padding(start = OpcSpacing.s) else Modifier,
            )
        }
    }
}

/** 离线提示条：只在拿的是演示/缓存数据时出现，写明最后同步时刻。 */
@Composable
internal fun OfflineBar(linkState: LinkState, lastSync: String) {
    if (linkState != LinkState.OFFLINE) return
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.s),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
    ) {
        Icon(Icons.Default.Warning, contentDescription = null, tint = OpcGold, modifier = Modifier.size(14.dp))
        Text(
            text = "离线展示演示数据 · 最后同步 " + lastSync,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/** 通用卡片容器。 */
@Composable
internal fun LocalCard(
    modifier: Modifier = Modifier,
    background: Color = MaterialTheme.colorScheme.surfaceContainerLow,
    padding: PaddingValues = PaddingValues(horizontal = OpcSpacing.l, vertical = OpcSpacing.m),
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(CardRadius))
            .background(background)
            .padding(padding),
        content = content,
    )
}

/** 聊天气泡：自己发的主色实底，机器人来的容器底，尖角朝发送方。 */
@Composable
internal fun LocalBubble(text: String, mine: Boolean) {
    val scheme = MaterialTheme.colorScheme
    val shape = if (mine) {
        RoundedCornerShape(18.dp, 18.dp, 6.dp, 18.dp)
    } else {
        RoundedCornerShape(18.dp, 18.dp, 18.dp, 6.dp)
    }
    Column(
        modifier = Modifier
            .clip(shape)
            .background(if (mine) scheme.primary else scheme.surfaceContainerLow)
            .padding(horizontal = 14.dp, vertical = 11.dp),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = if (mine) scheme.onPrimary else scheme.onSurface,
        )
    }
}


/** 设置/连接信息里的键值行。 */
@Composable
internal fun LocalKeyValueRow(
    key: String,
    value: String,
    valueColor: Color = MaterialTheme.colorScheme.onSurfaceVariant,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m),
    ) {
        Text(key, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
        Spacer(Modifier.weight(1f))
        Text(
            text = value,
            style = MaterialTheme.typography.labelMedium,
            color = valueColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(end = if (trailing == null) 0.dp else OpcSpacing.s),
        )
        trailing?.invoke()
    }
}

/** 开关行（白名单里的开关只有本地态，不落后端）。 */
@Composable
internal fun LocalSwitchRow(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.weight(1f),
        )
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

/** 空状态：没有数据时给一句话和下一步，不留白屏。 */
@Composable
internal fun LocalEmptyState(title: String, hint: String) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(vertical = OpcSpacing.xxl),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier.size(56.dp).clip(RoundedCornerShape(20.dp)).background(MaterialTheme.colorScheme.surfaceContainerHigh),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Default.Warning,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(24.dp),
            )
        }
        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(top = OpcSpacing.m),
        )
        Text(
            hint,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

/** 等级色随角色码走（R0 红 / R1 金 / RX 靛），空闲一律中性。 */
internal fun roleTone(code: String, state: RoleState): TierTone = when {
    state == RoleState.IDLE -> TierTone.NEUTRAL
    state == RoleState.BLOCKED -> TierTone.R0
    code == "R0" -> TierTone.R0
    code == "R1" -> TierTone.R1
    else -> TierTone.RX
}

internal fun roleStateLabel(state: RoleState): String = when (state) {
    RoleState.COMMANDING -> "指挥中"
    RoleState.RUNNING -> "跑"
    RoleState.IDLE -> "闲"
    RoleState.BLOCKED -> "阻塞"
}


internal fun eventTone(kind: EventKind): EventTone = when (kind) {
    EventKind.DONE -> EventTone.DONE
    EventKind.ERROR -> EventTone.ERROR
    EventKind.INFO -> EventTone.INFO
}

/** 离线提示条要写的「最后同步 HH:mm」。 */
internal fun nowHm(): String = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())

internal fun fmtYuan(value: Double): String = "¥" + String.format(Locale.US, "%.2f", value)

internal fun fmtTokens(value: Long): String = when {
    value >= 1_000_000 -> String.format(Locale.US, "%.2fM", value / 1_000_000.0)
    value >= 1_000 -> String.format(Locale.US, "%.1fk", value / 1_000.0)
    else -> value.toString()
}
