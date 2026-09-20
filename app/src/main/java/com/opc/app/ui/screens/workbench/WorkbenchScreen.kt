package com.opc.app.ui.screens.workbench

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.opc.app.domain.ChatItem
import com.opc.app.ui.components.AvatarCircle
import com.opc.app.ui.components.CapsuleChip
import com.opc.app.ui.components.StatusBarSpacer
import com.opc.app.ui.components.TierTag
import com.opc.app.ui.components.TierTone
import com.opc.app.ui.screens.LocalBubble
import com.opc.app.ui.screens.LocalSubTaskCard
import com.opc.app.ui.screens.OfflineBar
import com.opc.app.ui.theme.OpcGold
import com.opc.app.ui.theme.OpcGreen
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing

/** 快捷芯片的三种意图，落到输入框前缀上。 */
private val QuickIntents: List<Pair<String, String>> = listOf(
    "立即执行" to "立即执行：",
    "指派角色" to "指派给 R4：",
    "定时" to "定时到 18:00 后跑：",
)

@Composable
fun WorkbenchScreen(factory: ViewModelProvider.Factory) {
    val viewModel: WorkbenchViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        StatusBarSpacer()
        GroupHeader(members = state.members)
        OfflineBar(linkState = state.linkState, lastSync = state.lastSync)

        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            items(items = state.items, key = { it.id }) { item -> ChatRow(item) }
        }

        Composer(state = state, viewModel = viewModel)
    }
}

@Composable
private fun GroupHeader(members: List<String>) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.s),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            members.take(3).forEachIndexed { index, code ->
                AvatarCircle(
                    text = code,
                    tone = avatarTone(code),
                    size = 30.dp,
                    modifier = if (index == 0) Modifier else Modifier.padding(start = (-9).dp),
                )
            }
            if (members.size > 3) {
                Box(
                    Modifier
                        .padding(start = (-9).dp)
                        .size(30.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceContainerHigh),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "+" + (members.size - 3),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        Column(Modifier.weight(1f)) {
            Text("R1 老板助理", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                Box(Modifier.size(7.dp).clip(CircleShape).background(OpcGreen))
                Text(
                    "在线 · " + members.size + " 个角色在群",
                    style = MaterialTheme.typography.labelSmall,
                    color = OpcGreen,
                )
            }
        }
        IconButton(onClick = { }) {
            Icon(Icons.Default.MoreVert, contentDescription = "更多", tint = MaterialTheme.colorScheme.onSurface)
        }
    }
}

@Composable
private fun ChatRow(item: ChatItem) {
    when (item) {
        is ChatItem.DayDivider -> DayDivider(item.text)
        is ChatItem.SystemLine -> SystemLine(item)
        is ChatItem.Mine -> MineRow(item)
        is ChatItem.Agent -> AgentRow(item)
        is ChatItem.Subtasks -> Column(
            modifier = Modifier.fillMaxWidth().padding(start = 39.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            item.items.forEach { sub -> LocalSubTaskCard(sub) }
        }
        is ChatItem.Progress -> ProgressRow(item)
    }
}

@Composable
private fun DayDivider(text: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.weight(1f).height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))
        Text(text, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box(Modifier.weight(1f).height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))
    }
}

@Composable
private fun SystemLine(item: ChatItem.SystemLine) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(start = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Box(Modifier.size(7.dp).clip(CircleShape).background(OpcGold))
        Text(item.text + " · " + item.time, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MineRow(item: ChatItem.Mine) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Spacer(Modifier.weight(1f))
        Column(horizontalAlignment = Alignment.End) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                Text(item.time, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("你", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
            }
            Spacer(Modifier.height(5.dp))
            LocalBubble(text = item.text, mine = true)
        }
        AvatarCircle(text = "你", tone = TierTone.NEUTRAL, size = 30.dp)
    }
}

@Composable
private fun AgentRow(item: ChatItem.Agent) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        AvatarCircle(text = item.avatar, tone = avatarTone(item.avatar), size = 30.dp)
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                Text(item.who, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
                Text(item.time, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(5.dp))
            LocalBubble(text = item.text, mine = false)
        }
    }
}

@Composable
private fun ProgressRow(item: ChatItem.Progress) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        AvatarCircle(text = item.avatar, tone = avatarTone(item.avatar), size = 30.dp)
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                Text(item.who, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
                Text(
                    (item.progress * 100).toInt().toString() + "% · " + item.rounds + " 轮",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(5.dp))
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(androidx.compose.foundation.shape.RoundedCornerShape(18.dp))
                    .background(MaterialTheme.colorScheme.surfaceContainerLow)
                    .padding(horizontal = 14.dp, vertical = 12.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                    TierTag(item.subNo, TierTone.RX)
                    Spacer(Modifier.weight(1f))
                    Text(item.rounds.toString() + " 轮", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(
                    item.text,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = OpcSpacing.s),
                )
                LinearProgressIndicator(
                    progress = { item.progress.coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(6.dp).clip(CircleShape),
                    color = OpcGold,
                )
            }
        }
    }
}

@Composable
private fun Composer(state: WorkbenchUiState, viewModel: WorkbenchViewModel) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.background)
            .imePadding()
            .padding(horizontal = OpcSpacing.m, vertical = OpcSpacing.s),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
            QuickIntents.forEach { (label, prefix) ->
                CapsuleChip(text = label, onClick = { viewModel.applyQuickIntent(prefix) })
            }
        }
        Spacer(Modifier.height(OpcSpacing.s))
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
            OutlinedTextField(
                value = state.draft,
                onValueChange = viewModel::onDraftChange,
                placeholder = { Text("下达任务，或回复 R1…") },
                maxLines = 4,
                modifier = Modifier.weight(1f),
            )
            IconButton(
                onClick = viewModel::send,
                enabled = state.draft.isNotBlank() && !state.sending,
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary),
            ) {
                Icon(Icons.Default.Send, contentDescription = "发送", tint = MaterialTheme.colorScheme.onPrimary)
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 6.dp, start = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Box(Modifier.size(7.dp).clip(CircleShape).background(OpcGreen))
            Text("自动执行链运行中", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.weight(1f))
            Text(
                state.error ?: "峰时 · 长任务排谷时",
                style = MaterialTheme.typography.labelSmall,
                color = if (state.error == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error,
            )
        }
    }
}

private fun avatarTone(code: String): TierTone = when {
    code == "R0" -> TierTone.R0
    code == "R1" -> TierTone.R1
    code.length <= 2 -> TierTone.NEUTRAL
    else -> TierTone.RX
}
