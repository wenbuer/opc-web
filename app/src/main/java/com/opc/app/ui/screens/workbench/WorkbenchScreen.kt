package com.opc.app.ui.screens.workbench

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.opc.app.domain.ActivityAction
import com.opc.app.domain.TaskActivity
import com.opc.app.domain.TaskDiary
import com.opc.app.domain.TaskStatus
import com.opc.app.ui.components.CapsuleChip
import com.opc.app.ui.components.StatusBarSpacer
import com.opc.app.ui.components.imeBottomPadding
import com.opc.app.ui.components.TierTag
import com.opc.app.ui.components.TierTone
import com.opc.app.ui.screens.OfflineBar
import com.opc.app.ui.theme.OpcGold
import com.opc.app.ui.theme.OpcGreen
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing

/**
 * 工作台 = 全任务的流水屏。
 * 每一条只回答「谁在什么时候做了什么」：R1 拆分 / RX 接收 / RX 完成 / R1 汇报。
 * 执行细节（工具调用、轮数、产出正文）不在这里展开 —— 那是任务详情与产出的活。
 */
@Composable
fun WorkbenchScreen(factory: ViewModelProvider.Factory) {
    val viewModel: WorkbenchViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()
    val listState = rememberLazyListState()

    // 新任务下达后滚到底，不让人自己找
    LaunchedEffect(state.diaries.size) {
        if (state.diaries.isNotEmpty()) listState.animateScrollToItem(state.diaries.lastIndex)
    }

    Column(Modifier.fillMaxSize()) {
        StatusBarSpacer()
        LocalWorkbenchBar()
        OfflineBar(linkState = state.linkState, lastSync = state.lastSync)

        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth(),
            state = listState,
            contentPadding = PaddingValues(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
            verticalArrangement = Arrangement.spacedBy(OpcSpacing.m),
        ) {
            items(items = state.diaries, key = { it.taskNo }) { diary -> DiarRow(diary) }
        }

        Composer(state = state, viewModel = viewModel)
    }
}

/** 群名做成一行细标题，不再显示头像堆、在线状态这类没有信息量的东西。 */
@Composable
internal fun LocalWorkbenchBar() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.s),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("工作台", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
        Spacer(Modifier.weight(1f))
        Text("全部任务 · 时间顺序", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
internal fun DiarRow(diary: TaskDiary) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerLow)
            .padding(horizontal = 14.dp, vertical = 12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
            TierTag(text = diary.taskNo, tone = TierTone.RX)
            Spacer(Modifier.weight(1f))
            TierTag(text = statusLabel(diary.status), tone = statusTone(diary.status))
        }
        Text(
            diary.text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(top = OpcSpacing.s),
        )
        HorizontalDivider(
            color = MaterialTheme.colorScheme.outlineVariant,
            modifier = Modifier.padding(top = OpcSpacing.m, bottom = OpcSpacing.xs),
        )
        diary.activities.forEach { act -> ActivityLine(act) }
    }
}

/** 一条动作：竖线 + 圆点 + 「谁 + 动作 + 对象」，行尾时间。 */
@Composable
internal fun ActivityLine(act: TaskActivity) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
    ) {
        Box(Modifier.padding(top = 6.dp).size(7.dp).clip(CircleShape).background(dotColor(act.action)))
        Column(Modifier.weight(1f)) {
            Text(
                headline(act),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
            if (act.targetName != null) {
                Text(
                    act.targetName,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 2.dp),
                )
            }
        }
        Text(
            act.time,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

private fun headline(act: TaskActivity): String {
    val who = act.subjectName + " " + act.subject
    val what = when (act.action) {
        ActivityAction.ASSIGNED -> "下达任务"
        ActivityAction.DECOMPOSED -> "拆分任务"
        ActivityAction.ACCEPTED -> "接收任务"
        ActivityAction.COMPLETED -> "完成任务"
        ActivityAction.REPORTED -> "汇报任务"
    }
    val target = act.target?.let { " · " + it }.orEmpty()
    return who + " " + what + target
}

@Composable
private fun dotColor(action: ActivityAction) = when (action) {
    ActivityAction.DECOMPOSED -> OpcGold
    ActivityAction.ACCEPTED -> MaterialTheme.colorScheme.secondary
    ActivityAction.COMPLETED -> OpcGreen
    ActivityAction.REPORTED -> MaterialTheme.colorScheme.primary
    ActivityAction.ASSIGNED -> OpcGold
}

private fun statusLabel(status: TaskStatus) = when (status) {
    TaskStatus.QUEUED -> "待派"
    TaskStatus.DECOMPOSING -> "拆解中"
    TaskStatus.RUNNING -> "进行中"
    TaskStatus.DONE -> "已完成"
    TaskStatus.BLOCKED -> "阻塞"
}

private fun statusTone(status: TaskStatus) = when (status) {
    TaskStatus.DONE -> TierTone.OK
    TaskStatus.BLOCKED -> TierTone.R0
    TaskStatus.RUNNING, TaskStatus.DECOMPOSING -> TierTone.R1
    TaskStatus.QUEUED -> TierTone.NEUTRAL
}

/**
 * 输入区。高度构成（行高 = 组件本身，不含字重导致的行盒溢出）：
 *   上分隔线 1dp
 *   + 上内边距 6dp
 *   + 药丸 54dp（8dp padding 上下 + 38dp 单行输入框；长文本每添一行 +14dp，最多 4 行）
 *   + 状态行 6dp(top) + 14dp(lineHeight) = 20dp
 *   + 下内边距 6dp
 *   = 1 + 6 + 54 + 20 + 6 = 约 81dp（输入长到 4 行时 +42dp）。
 * 原来那版：快捷芯片 32 + 间距 8 + 56dp 起步的 OutlinedTextField + 状态行 21 + 内外边距 32
 * ≈ 150dp。上面不再挂快捷芯片行，药丸底下也不再挂角色行 —— 两行都搬进了「+」的底部弹层。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun Composer(state: WorkbenchUiState, viewModel: WorkbenchViewModel) {
    var sheetOpen by remember { mutableStateOf(false) }
    val sheetState = rememberModalBottomSheetState()

    Column(
        Modifier
            .fillMaxWidth()
            // 键盘弹起时把输入区顶上去；只补「键盘高出导航栏」的那一段，避免和底栏重复占位
            .imeBottomPadding(),
    ) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Column(Modifier.padding(horizontal = OpcSpacing.m, vertical = 6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(26.dp))
                        .background(MaterialTheme.colorScheme.surfaceContainer)
                        .padding(start = 16.dp, end = 4.dp, top = 8.dp, bottom = 8.dp),
                ) {
                    BasicTextField(
                        value = state.draft,
                        onValueChange = viewModel::onDraftChange,
                        textStyle = MaterialTheme.typography.bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface),
                        cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                        // 单行不撑高：这是把整块输入区压回设计图高度的关键，M3 输入框的 56dp 起步底高不要了
                        minLines = 1,
                        maxLines = 4,
                        decorationBox = { inner ->
                            Box(
                                modifier = Modifier.heightIn(min = 38.dp).fillMaxWidth(),
                                contentAlignment = Alignment.CenterStart,
                            ) {
                                if (state.draft.isEmpty()) {
                                    Text(
                                        "下达任务，@ 指派角色…",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        maxLines = 1,
                                    )
                                }
                                inner()
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }

                // 「+」＝原来的 @ 行列：三个快捷意图 + 角色列表，都收进弹层
                IconButton(
                    onClick = { sheetOpen = true },
                    modifier = Modifier.size(36.dp).clip(CircleShape),
                ) {
                    Icon(Icons.Default.Add, contentDescription = "快捷意图与指派角色", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }

                IconButton(
                    onClick = viewModel::send,
                    enabled = state.draft.isNotBlank() && !state.sending,
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary),
                ) {
                    Icon(
                        Icons.Default.Send,
                        contentDescription = "发送",
                        tint = if (state.draft.isNotBlank() && !state.sending) {
                            MaterialTheme.colorScheme.onPrimary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
            }

            // 只留峰时/错误这半句：链路是否在跑已经在总览与「我的」里说过了
            Text(
                state.error ?: "峰时 · 长任务排谷时",
                style = MaterialTheme.typography.labelSmall,
                color = if (state.error == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 6.dp, start = 2.dp),
            )
        }
    }

    if (sheetOpen) {
        ModalBottomSheet(
            onDismissRequest = { sheetOpen = false },
            sheetState = sheetState,
            containerColor = MaterialTheme.colorScheme.surfaceContainer,
        ) {
            IntentSheet(
                roles = state.roles,
                onIntent = { prefix ->
                    viewModel.appendQuickIntent(prefix)
                    sheetOpen = false
                },
                onPickRole = { code ->
                    viewModel.pickMention(code)
                    sheetOpen = false
                },
            )
        }
    }
}

/** 弹层内容：上组是三个快捷意图（只写前缀，发不发仍由人过一眼），下组是「@」能点到的角色。 */
@Composable
internal fun IntentSheet(
    roles: List<Pair<String, String>>,
    onIntent: (String) -> Unit,
    onPickRole: (String) -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = OpcScreenPadding)
            .padding(bottom = OpcSpacing.xl),
        verticalArrangement = Arrangement.spacedBy(OpcSpacing.m),
    ) {
        Text("快捷意图", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
        Row(
            modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            QuickIntents.forEach { (label, prefix) ->
                CapsuleChip(text = label, onClick = { onIntent(prefix) })
            }
        }
        Text("指派给", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
        if (roles.isEmpty()) {
            Text("角色列表未加载", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            Row(
                modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                roles.forEach { (code, name) ->
                    CapsuleChip(text = code + " " + name, onClick = { onPickRole(code) })
                }
            }
        }
    }
}

/** 「@」挑角色：点谁就把谁写进输入框，不猜也不要人记编号。 */
@Composable
internal fun MentionRow(roles: List<Pair<String, String>>, onPick: (String) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Text("指派给", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (roles.isEmpty()) {
            Text("角色列表未加载", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        roles.take(4).forEach { (code, name) ->
            CapsuleChip(text = code + " " + name, onClick = { onPick(code) })
        }
    }
}

/** 快捷芯片的三种意图，落到输入框前缀上。 */
internal val QuickIntents: List<Pair<String, String>> = listOf(
    "立即执行" to "立即执行：",
    "指派角色" to "指派给 @",
    "定时" to "定时到 18:00 后跑：",
)