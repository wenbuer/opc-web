package com.opc.app.ui.screens.review

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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.opc.app.domain.PendingItem
import com.opc.app.domain.TaskStatus
import com.opc.app.domain.TaskSummary
import com.opc.app.domain.Verdict
import com.opc.app.ui.components.CapsuleChip
import com.opc.app.ui.components.EventRow
import com.opc.app.ui.components.GhostChip
import com.opc.app.ui.components.MetricCard
import com.opc.app.ui.components.MetricTone
import com.opc.app.ui.components.TierTag
import com.opc.app.ui.components.TierTone
import com.opc.app.ui.screens.LocalCard
import com.opc.app.ui.screens.LocalEmptyState
import com.opc.app.ui.screens.LocalSectionHeader
import com.opc.app.ui.screens.LocalTopBar
import com.opc.app.ui.screens.OfflineBar
import com.opc.app.ui.theme.OpcRed
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing

/** 驳回和修改都要先把意见写清楚，批准不用。 */
private enum class OpinionDialog { REJECT, AMEND }

@Composable
fun ReviewScreen(factory: ViewModelProvider.Factory) {
    val viewModel: ReviewViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()
    var dialog by remember { mutableStateOf<OpinionDialog?>(null) }
    val focus = state.pending.firstOrNull()

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        LocalTopBar(title = "批阅台") {
            GhostChip(text = "按等待排序", showChevron = true)
        }
        OfflineBar(linkState = state.linkState, lastSync = state.lastSync)

        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = OpcScreenPadding),
        ) {
            Spacer(Modifier.height(OpcSpacing.s))
            Row(horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                MetricCard(state.pending.size.toString(), "待裁决", MetricTone.ALERT, Modifier.weight(1f))
                MetricCard(
                    state.tasks.count { it.status == TaskStatus.DONE }.toString(),
                    "待批阅",
                    MetricTone.GOLD,
                    Modifier.weight(1f),
                )
                MetricCard(
                    state.tasks.count { it.status == TaskStatus.RUNNING }.toString(),
                    "在跑",
                    MetricTone.NEUTRAL,
                    Modifier.weight(1f),
                )
            }

            val longest = state.pending.maxByOrNull { it.waitedHours }
            if (longest != null && longest.waitedHours > 0) {
                Spacer(Modifier.height(OpcSpacing.m))
                LocalCard(background = MaterialTheme.colorScheme.errorContainer) {
                    Row(horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = OpcRed, modifier = Modifier.size(18.dp))
                        Text(
                            text = "有 " + state.pending.size + " 项决策已等待 " + longest.waitedHours + " 小时，" +
                                "下游子任务 " + longest.taskNo + "-" + longest.subNo + " 已排队等它放行。",
                            style = MaterialTheme.typography.bodySmall,
                            color = OpcRed,
                        )
                    }
                }
            }

            LocalSectionHeader(
                title = "决策裁决",
                meta = if (state.pending.isEmpty()) "0 / 0" else "1 / " + state.pending.size,
            )
            if (state.pending.isEmpty()) {
                LocalEmptyState("没有等你裁决的事", "子任务回报里没人卡住，批阅台就是空的")
            } else {
                state.pending.forEach { item ->
                    PendingCard(
                        item = item,
                        chosen = state.choices[pendingKey(item)] ?: -1,
                        onChoose = { index -> viewModel.choose(pendingKey(item), index) },
                    )
                    Spacer(Modifier.height(OpcSpacing.m))
                }
            }

            LocalSectionHeader(
                title = "工作内容",
                meta = state.tasks.count { it.status == TaskStatus.DONE }.toString() + " 条待阅",
                action = "全部归档",
            )
            LocalCard(padding = PaddingValues(horizontal = 14.dp, vertical = 4.dp)) {
                if (state.tasks.isEmpty()) {
                    EventRow(time = "--:--", text = "还没有产出归档")
                } else {
                    state.tasks.forEach { task -> TaskRow(task) }
                }
            }
            Spacer(Modifier.height(OpcSpacing.xl))
        }

        state.error?.let { message ->
            Row(
                Modifier.fillMaxWidth().padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.xs),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(message, style = MaterialTheme.typography.labelMedium, color = OpcRed, modifier = Modifier.weight(1f))
                TextButton(onClick = viewModel::dismissError) { Text("知道了") }
            }
        }

        VerdictBar(
            enabled = focus != null && !state.submitting,
            submitting = state.submitting,
            onApprove = { focus?.let { viewModel.submit(Verdict.APPROVE, "") } },
            onReject = { dialog = OpinionDialog.REJECT },
            onAmend = { dialog = OpinionDialog.AMEND },
        )
    }

    if (dialog != null) {
        OpinionDialogContent(
            mode = dialog!!,
            onDismiss = { dialog = null },
            onConfirm = { opinion ->
                viewModel.submit(if (dialog == OpinionDialog.REJECT) Verdict.REJECT else Verdict.AMEND, opinion)
                dialog = null
            },
        )
    }
}

@Composable
private fun PendingCard(item: PendingItem, chosen: Int, onChoose: (Int) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Column(
        Modifier
            .fillMaxWidth()
            .background(scheme.surfaceContainerLow, RoundedCornerShape(0.dp, 18.dp, 18.dp, 0.dp))
            .padding(horizontal = OpcSpacing.l, vertical = OpcSpacing.m),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
            TierTag(item.taskNo, TierTone.R1)
            TierTag(item.subNo, TierTone.R1)
            Spacer(Modifier.weight(1f))
            Text(
                item.proposedBy + " · " + item.proposedAt + " 提出",
                style = MaterialTheme.typography.labelSmall,
                color = scheme.onSurfaceVariant,
            )
        }
        Text(
            item.title,
            style = MaterialTheme.typography.titleMedium,
            color = scheme.onSurface,
            modifier = Modifier.padding(top = 10.dp, bottom = OpcSpacing.s),
        )
        Text(item.summary, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
        if (item.risk.isNotBlank()) {
            Text(
                item.risk,
                style = MaterialTheme.typography.labelMedium,
                color = OpcRed,
                modifier = Modifier.padding(top = OpcSpacing.xs),
            )
        }

        Column(
            Modifier
                .padding(top = 14.dp)
                .fillMaxWidth()
                .background(scheme.surfaceContainerHigh, RoundedCornerShape(14.dp))
                .padding(horizontal = 13.dp, vertical = OpcSpacing.m),
        ) {
            Text(
                "R1 决策建议",
                style = MaterialTheme.typography.labelMedium,
                color = scheme.onSurfaceVariant,
                modifier = Modifier.padding(bottom = OpcSpacing.s),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                TierTag("推荐 " + item.recommend, TierTone.R1)
                Text(
                    item.recommendWhy,
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onSurface,
                )
            }
            if (item.options.isNotEmpty()) {
                Spacer(Modifier.height(11.dp))
                Column(verticalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                    item.options.forEachIndexed { index, option ->
                        CapsuleChip(
                            text = option,
                            selected = index == chosen,
                            onClick = { onChoose(index) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TaskRow(task: TaskSummary) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m),
    ) {
        Box(
            Modifier.size(38.dp).background(scheme.tertiaryContainer, RoundedCornerShape(12.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Default.Check, contentDescription = null, tint = scheme.tertiary, modifier = Modifier.size(17.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(
                task.taskNo + " " + task.text,
                style = MaterialTheme.typography.titleSmall,
                color = scheme.onSurface,
                maxLines = 1,
            )
            Text(
                task.createdAt + " · " + task.subtasks.size + " 子任务 · " + taskStatusLabel(task.status),
                style = MaterialTheme.typography.labelSmall,
                color = scheme.onSurfaceVariant,
            )
        }
        Text("阅", style = MaterialTheme.typography.labelMedium, color = scheme.secondary)
    }
}

@Composable
private fun VerdictBar(
    enabled: Boolean,
    submitting: Boolean,
    onApprove: () -> Unit,
    onReject: () -> Unit,
    onAmend: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Button(
            onClick = onReject,
            enabled = enabled,
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.error,
                contentColor = MaterialTheme.colorScheme.onError,
            ),
            contentPadding = PaddingValues(horizontal = 12.dp),
            modifier = Modifier.weight(1f),
        ) { Text("驳回") }
        OutlinedButton(
            onClick = onAmend,
            enabled = enabled,
            contentPadding = PaddingValues(horizontal = 12.dp),
            modifier = Modifier.weight(1f),
        ) { Text("修改") }
        Button(
            onClick = onApprove,
            enabled = enabled,
            contentPadding = PaddingValues(horizontal = 12.dp),
            modifier = Modifier.weight(1f),
        ) {
            if (submitting) {
                CircularProgressIndicator(Modifier.size(15.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(OpcSpacing.s))
            }
            Text("批准")
        }
    }
}

@Composable
private fun OpinionDialogContent(mode: OpinionDialog, onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var opinion by remember { mutableStateOf("") }
    val isReject = mode == OpinionDialog.REJECT
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (isReject) "驳回并说明理由" else "修改后重跑，写清改什么") },
        text = {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                    Icon(Icons.Default.Info, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
                    Text(
                        if (isReject) "意见会回给提案的角色，任务按阻塞收口。" else "意见会作为追加条件并入下一轮执行。",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                OutlinedTextField(
                    value = opinion,
                    onValueChange = { opinion = it },
                    placeholder = { Text("至少写一句，别让角色猜") },
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth().padding(top = OpcSpacing.m).heightIn(min = 96.dp),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(opinion.trim()) }, enabled = opinion.isNotBlank()) {
                Text(if (isReject) "驳回" else "提交修改", color = if (isReject) OpcRed else MaterialTheme.colorScheme.primary)
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

private fun taskStatusLabel(status: TaskStatus): String = when (status) {
    TaskStatus.QUEUED -> "排队"
    TaskStatus.DECOMPOSING -> "拆解中"
    TaskStatus.RUNNING -> "跑"
    TaskStatus.DONE -> "已归档"
    TaskStatus.BLOCKED -> "阻塞"
}
