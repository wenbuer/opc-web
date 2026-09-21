package com.opc.app.ui.screens.overview

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import com.opc.app.domain.RoleStatus
import com.opc.app.tunnel.TunnelState
import com.opc.app.ui.components.AvatarCircle
import com.opc.app.ui.components.CapsuleChip
import com.opc.app.ui.components.EventRow
import com.opc.app.ui.components.GhostChip
import com.opc.app.ui.components.HeroCard
import com.opc.app.ui.components.MetricCard
import com.opc.app.ui.components.MetricTone
import com.opc.app.ui.components.SparkBars
import com.opc.app.ui.components.TierTag
import com.opc.app.ui.screens.LocalCard
import com.opc.app.ui.screens.LocalEmptyState
import com.opc.app.ui.screens.LocalSectionHeader
import com.opc.app.ui.screens.LocalTopBar
import com.opc.app.ui.screens.OfflineBar
import com.opc.app.ui.screens.eventTone
import com.opc.app.ui.screens.fmtTokens
import com.opc.app.ui.screens.fmtYuan
import com.opc.app.ui.screens.roleStateLabel
import com.opc.app.ui.screens.roleTone
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun OverviewScreen(factory: ViewModelProvider.Factory) {
    val viewModel: OverviewViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()
    val stats = state.stats

    Column(Modifier.fillMaxSize()) {
        LocalTopBar(title = "作战面板") {
            IconButton(onClick = viewModel::refresh) {
                Icon(Icons.Default.Refresh, contentDescription = "刷新", tint = MaterialTheme.colorScheme.onSurface)
            }
            Box {
                IconButton(onClick = { }) {
                    Icon(Icons.Default.Notifications, contentDescription = "通知", tint = MaterialTheme.colorScheme.onSurface)
                }
                if ((stats?.pendingReview ?: 0) > 0) {
                    Box(
                        Modifier
                            .padding(top = 10.dp, end = 10.dp)
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.error)
                            .align(Alignment.TopEnd),
                    )
                }
            }
        }
        OfflineBar(linkState = state.linkState, lastSync = state.lastSync)

        if (stats == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                if (state.loading) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                } else {
                    LocalEmptyState("这屏暂时没有数据", "下拉刷新或检查服务端连接")
                }
            }
            return@Column
        }

        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = OpcScreenPadding),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(bottom = OpcSpacing.m),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
            ) {
                CapsuleChip(text = state.project?.name ?: "未选项目", selected = true)
                GhostChip(text = "已连接 " + (state.host ?: "服务端"), leadingDot = true)
                // 隧道芯片：点一下重连；失败态用红底把它从「服务端不在线」里区分出来
                CapsuleChip(
                    text = "隧道 " + state.tunnel.label,
                    selected = state.tunnel.state == TunnelState.UP,
                    hot = state.tunnel.state == TunnelState.ERROR,
                    onClick = viewModel::reconnectTunnel,
                )
            }

            HeroCard(
                title = heroTitle(stats.doneToday, stats.pendingReview),
                subtitle = "成本 " + fmtYuan(stats.costTodayYuan) + " · Token " + fmtTokens(stats.tokensToday) + " · 峰时 2 项已排到谷时",
                trailing = SimpleDateFormat("MM-dd", Locale.getDefault()).format(Date()),
            ) {
                SparkBars(values = stats.weekCosts, highlightLast = true)
            }

            Row(
                modifier = Modifier.fillMaxWidth().padding(top = OpcSpacing.m),
                horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
            ) {
                MetricCard(stats.doneToday.toString(), "今日完成", MetricTone.NEUTRAL, Modifier.weight(1f))
                MetricCard(stats.pendingReview.toString(), "待裁决", MetricTone.ALERT, Modifier.weight(1f))
                MetricCard(stats.running.toString(), "在跑", MetricTone.GOLD, Modifier.weight(1f))
            }

            LocalSectionHeader(title = "组织", meta = stats.roles.size.toString() + " ROLES", action = "全部")
            LocalCard(padding = PaddingValues(horizontal = 14.dp, vertical = 4.dp)) {
                stats.roles.forEachIndexed { index, role ->
                    if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    RoleRow(role)
                }
            }

            LocalSectionHeader(title = "实时事件", action = "工作台")
            Column(Modifier.padding(start = 2.dp, bottom = OpcSpacing.xl)) {
                stats.events.forEach { event ->
                    EventRow(time = event.time, text = event.text, tone = eventTone(event.kind))
                }
            }
        }
    }
}

@Composable
private fun RoleRow(role: RoleStatus) {
    val tone = roleTone(role.code, role.state)
    val large = role.code == "R0" || role.code == "R1"
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m),
    ) {
        AvatarCircle(text = role.code, tone = tone, size = if (large) 38.dp else 30.dp)
        Column(Modifier.weight(1f)) {
            Text(role.name, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
            Text(
                role.note,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
        }
        TierTag(text = roleStateLabel(role.state), tone = tone)
    }
}

private fun heroTitle(done: Int, pendingReview: Int): String =
    "今日 " + done + " 个子任务完成，" + pendingReview + " 项待你裁决"

