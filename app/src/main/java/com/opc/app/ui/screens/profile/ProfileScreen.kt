package com.opc.app.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.opc.app.data.LinkState
import com.opc.app.ui.components.AvatarCircle
import com.opc.app.ui.components.TierTag
import com.opc.app.ui.components.TierTone
import com.opc.app.ui.screens.LocalCard
import com.opc.app.ui.screens.LocalKeyValueRow
import com.opc.app.ui.screens.LocalSectionHeader
import com.opc.app.ui.screens.LocalSwitchRow
import com.opc.app.ui.screens.LocalTopBar
import com.opc.app.ui.screens.OfflineBar
import com.opc.app.ui.theme.OpcGreen
import com.opc.app.ui.theme.OpcRed
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing

@Composable
fun ProfileScreen(factory: ViewModelProvider.Factory) {
    val viewModel: ProfileViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()
    val config = state.config

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        LocalTopBar(
            title = "我的",
            subtitle = config?.deviceName,
        )
        OfflineBar(linkState = state.linkState, lastSync = state.lastSync)

        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = OpcScreenPadding),
        ) {
            Spacer(Modifier.height(OpcSpacing.m))
            LocalCard(padding = PaddingValues(OpcScreenPadding)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m)) {
                    AvatarCircle(text = "R0", tone = TierTone.R0, size = 46.dp)
                    Column(Modifier.weight(1f)) {
                        Text("创始人", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
                        Text(
                            config?.deviceName ?: "未配对",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (state.linkState == LinkState.ONLINE) {
                        TierTag("在线", TierTone.OK)
                    } else {
                        TierTag("离线", TierTone.NEUTRAL)
                    }
                }
                Row(
                    modifier = Modifier.padding(top = 14.dp),
                    horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
                ) {
                    OutlinedButton(onClick = viewModel::refresh, modifier = Modifier.weight(1f)) { Text("刷新连接") }
                    OutlinedButton(onClick = viewModel::requestUnpair, modifier = Modifier.weight(1f)) { Text("重扫码") }
                }
            }

            LocalSectionHeader(title = "服务端连接", meta = "1 台")
            LocalCard(padding = PaddingValues(horizontal = OpcScreenPadding, vertical = 4.dp)) {
                LocalKeyValueRow("地址", config?.baseUrl ?: "未连接")
                LocalKeyValueRow("当前项目", state.project?.name ?: "未选择", valueColor = MaterialTheme.colorScheme.primary)
                LocalKeyValueRow("设备码", config?.deviceCode ?: "--")
                LocalKeyValueRow(
                    key = "白名单状态",
                    value = if (config == null) "未登记" else "已登记 · 可吊销",
                    valueColor = if (config == null) OpcRed else OpcGreen,
                )
                LocalKeyValueRow(
                    key = "链路",
                    value = when (state.linkState) {
                        LinkState.ONLINE -> "局域网直连"
                        LinkState.CONNECTING -> "正在探测…"
                        LinkState.OFFLINE -> "服务端不可达 · 走演示数据"
                        LinkState.UNPAIRED -> "未配对"
                    },
                )
            }

            LocalSectionHeader(title = "通知", meta = "本机")
            LocalCard(padding = PaddingValues(horizontal = OpcScreenPadding, vertical = 4.dp)) {
                state.notifications.forEach { (label, checked) ->
                    LocalSwitchRow(label = label, checked = checked, onCheckedChange = { viewModel.toggleNotification(label) })
                }
            }

            LocalSectionHeader(title = "运行开关（远程改服务端）", meta = "直接写服务端")
            LocalCard(padding = PaddingValues(horizontal = OpcScreenPadding, vertical = 4.dp)) {
                LocalSwitchRow(
                    label = "自动执行链",
                    checked = state.autoChain,
                    onCheckedChange = viewModel::setAutoChain,
                )
                LocalSwitchRow(
                    label = "峰时长任务排谷时",
                    checked = state.offPeakQueue,
                    onCheckedChange = viewModel::setOffPeakQueue,
                )
                LocalKeyValueRow("执行引擎", "DSH（默认）")
            }

            state.error?.let { message ->
                Spacer(Modifier.height(OpcSpacing.m))
                LocalCard(background = MaterialTheme.colorScheme.errorContainer) {
                    Text(message, style = MaterialTheme.typography.labelMedium, color = OpcRed)
                }
            }

            Spacer(Modifier.height(OpcSpacing.l))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(18.dp))
                    .background(MaterialTheme.colorScheme.errorContainer)
                    .clickable(onClick = viewModel::requestUnpair)
                    .padding(OpcScreenPadding),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Icon(Icons.Default.Lock, contentDescription = null, tint = OpcRed, modifier = Modifier.size(18.dp))
                Text(
                    "解除配对（吊销本机令牌）",
                    style = MaterialTheme.typography.titleSmall,
                    color = OpcRed,
                    modifier = Modifier.weight(1f),
                )
                Icon(Icons.Default.KeyboardArrowRight, contentDescription = null, tint = OpcRed, modifier = Modifier.size(16.dp))
            }

            Box(Modifier.fillMaxWidth().padding(vertical = OpcSpacing.l), contentAlignment = Alignment.Center) {
                Text(
                    "OPC App v0.1 · 服务端 opc-web v" + (config?.serverVersion ?: "--"),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }

    if (state.confirmUnpair) {
        AlertDialog(
            onDismissRequest = viewModel::dismissUnpair,
            title = { Text("解除配对？") },
            text = {
                Text(
                    "本机令牌会被吊销，缓存的总览与消息一并清掉；" +
                        "下次进入要重新扫码或在服务端把设备码加回白名单。",
                )
            },
            confirmButton = {
                TextButton(onClick = viewModel::confirmUnpair) { Text("解除配对", color = OpcRed) }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissUnpair) { Text("再想想") }
            },
        )
    }
}
