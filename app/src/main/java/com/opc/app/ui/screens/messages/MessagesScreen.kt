package com.opc.app.ui.screens.messages

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.opc.app.domain.FeedItem
import com.opc.app.domain.FeedType
import com.opc.app.ui.components.CapsuleChip
import com.opc.app.ui.components.GhostChip
import com.opc.app.ui.screens.LocalEmptyState
import com.opc.app.ui.screens.LocalTopBar
import com.opc.app.ui.screens.OfflineBar
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing
import java.util.Calendar

@Composable
fun MessagesScreen(factory: ViewModelProvider.Factory) {
    val viewModel: MessagesViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        LocalTopBar(title = "消息") {
            GhostChip(text = "未读 " + state.feed.count { !it.read })
        }
        OfflineBar(linkState = state.linkState, lastSync = state.lastSync)

        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = OpcScreenPadding),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = OpcSpacing.m),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                FeedFilter.entries.forEach { filter ->
                    CapsuleChip(
                        text = filter.label,
                        selected = state.filter == filter,
                        onClick = { viewModel.selectFilter(filter) },
                    )
                }
            }

            val visible = state.feed.filter { state.filter.accepts(it.type) }
            if (visible.isEmpty()) {
                LocalEmptyState("这类消息还没有", "换个分类看看，或等 R1 发下一份简报")
            } else {
                groupByDay(visible).forEach { (day, items) ->
                    Text(
                        day,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = OpcSpacing.m, bottom = 10.dp),
                    )
                    items.forEach { item ->
                        FeedCard(
                            item = item,
                            expanded = state.expandedId == item.id,
                            onClick = { viewModel.toggleExpanded(item.id) },
                        )
                        Spacer(Modifier.height(10.dp))
                    }
                }
                Spacer(Modifier.height(OpcSpacing.xl))
            }
        }
    }
}

@Composable
private fun FeedCard(item: FeedItem, expanded: Boolean, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val accent = typeColor(item.type)
    val icon = typeIcon(item.type)
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .background(scheme.surface)
            .clickable(onClick = onClick)
            .padding(OpcScreenPadding),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
            Box(
                Modifier.size(30.dp).clip(RoundedCornerShape(10.dp)).background(accent.copy(alpha = 0.16f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = null, tint = accent, modifier = Modifier.size(16.dp))
            }
            Text(
                typeLabel(item.type),
                style = MaterialTheme.typography.titleSmall,
                color = scheme.onSurface,
                modifier = Modifier.weight(1f),
            )
            Text(item.time, style = MaterialTheme.typography.labelSmall, color = scheme.onSurfaceVariant)
            if (!item.read) {
                Box(Modifier.size(8.dp).clip(CircleShape).background(scheme.error))
            }
        }

        Text(
            item.title,
            style = MaterialTheme.typography.titleMedium,
            color = scheme.onSurface,
            modifier = Modifier.padding(top = 10.dp, bottom = 6.dp),
        )
        Text(
            item.body,
            style = MaterialTheme.typography.bodySmall,
            color = scheme.onSurfaceVariant,
            maxLines = if (expanded) Int.MAX_VALUE else 2,
        )

        if (item.chips.isNotEmpty()) {
            Row(
                modifier = Modifier.padding(top = OpcSpacing.m),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                item.chips.forEach { chip -> GhostChip(text = chip) }
            }
        }

        if (expanded) {
            Column(
                Modifier
                    .padding(top = OpcSpacing.m)
                    .fillMaxWidth()
                    .background(scheme.surfaceContainerHigh, RoundedCornerShape(14.dp))
                    .padding(horizontal = 13.dp, vertical = OpcSpacing.m),
            ) {
                Text(
                    "这条消息由 " + typeOwner(item.type) + " 发出，详情已在服务端归档；" +
                        "手机端只读，回复请去工作台。",
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.onSurfaceVariant,
                )
            }
        }
    }
}

/*
 * FeedItem 只有 HH:mm，没有日期字段。用「时刻晚于当前」判昨天是唯一能自洽的口径：
 * 演示数据里 23:41 那条正是昨晚的告警。
 */
private fun groupByDay(items: List<FeedItem>): List<Pair<String, List<FeedItem>>> {
    if (items.isEmpty()) return emptyList()
    val nowMinutes = Calendar.getInstance().let { it.get(Calendar.HOUR_OF_DAY) * 60 + it.get(Calendar.MINUTE) }
    val grouped = items.groupBy { item -> if (minutesOf(item.time) > nowMinutes) "昨天" else "今天" }
    return grouped.entries.sortedBy { if (it.key == "今天") 0 else 1 }.map { it.key to it.value }
}

private fun minutesOf(time: String): Int {
    val parts = time.split(":")
    val hour = parts.getOrNull(0)?.toIntOrNull() ?: 0
    val minute = parts.getOrNull(1)?.toIntOrNull() ?: 0
    return hour * 60 + minute
}

private fun typeLabel(type: FeedType): String = when (type) {
    FeedType.DAILY -> "每日简报"
    FeedType.OUTPUT -> "新产出"
    FeedType.KNOWLEDGE -> "知识库更新"
    FeedType.ALERT -> "系统告警"
    FeedType.SCHEDULE -> "定时任务"
}

private fun typeOwner(type: FeedType): String = when (type) {
    FeedType.DAILY -> "R1 老板助理"
    FeedType.OUTPUT -> "执行角色"
    FeedType.KNOWLEDGE -> "知识库角色"
    FeedType.ALERT -> "执行护栏"
    FeedType.SCHEDULE -> "排程器"
}

private fun typeIcon(type: FeedType): ImageVector = when (type) {
    FeedType.DAILY -> Icons.Default.Email
    FeedType.OUTPUT -> Icons.Default.List
    FeedType.KNOWLEDGE -> Icons.Default.Star
    FeedType.ALERT -> Icons.Default.Warning
    FeedType.SCHEDULE -> Icons.Default.DateRange
}

@Composable
private fun typeColor(type: FeedType): Color = when (type) {
    FeedType.DAILY -> MaterialTheme.colorScheme.primary
    FeedType.OUTPUT -> MaterialTheme.colorScheme.secondary
    FeedType.KNOWLEDGE -> MaterialTheme.colorScheme.tertiary
    FeedType.ALERT -> MaterialTheme.colorScheme.error
    FeedType.SCHEDULE -> MaterialTheme.colorScheme.onSurfaceVariant
}
