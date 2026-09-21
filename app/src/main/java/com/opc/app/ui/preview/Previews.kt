package com.opc.app.ui.preview

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.opc.app.data.DemoData
import com.opc.app.data.LinkState
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.ServerConfig
import com.opc.app.ui.screens.LocalCard
import com.opc.app.ui.screens.LocalEmptyState
import com.opc.app.ui.screens.LocalSectionHeader
import com.opc.app.ui.screens.LocalTopBar
import com.opc.app.ui.screens.OfflineBar
import com.opc.app.ui.screens.messages.MessagesContent
import com.opc.app.ui.screens.messages.MessagesUiState
import com.opc.app.ui.screens.overview.OverviewUiState
import com.opc.app.ui.screens.profile.ProfileContent
import com.opc.app.ui.screens.profile.ProfileUiState
import com.opc.app.ui.screens.profile.ProfileViewModel
import com.opc.app.ui.screens.workbench.DiarRow
import com.opc.app.ui.screens.workbench.LocalWorkbenchBar
import com.opc.app.ui.screens.workbench.MentionRow
import com.opc.app.ui.screens.workbench.WorkbenchUiState
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing
import com.opc.app.ui.theme.OpcTheme

/**
 * IDE 里可交互的界面预览（Android Studio / IntelliJ 右侧 Gutter 的 Preview 面板）。
 * 每个 @Preview 都自带演示数据，点开就能点按钮、看状态，不用装到手机上。
 * 注意：这里只渲染「静态内容」那一层，ViewModel 相关的交互（联网、上报）在真机验。
 */
private object Demo {
    val workbench = WorkbenchUiState(
        loading = false,
        offline = true,
        diaries = DemoData.taskDiaries(),
        roles = DemoData.roleNames.entries.map { it.key to it.value },
    )
    val overview = OverviewUiState(
        loading = false,
        offline = true,
        project = DemoData.project,
        host = "192.168.1.20:8901",
        stats = DemoData.overview(),
    )
}

@Composable
private fun Phone(content: @Composable () -> Unit) {
    // 浅色 = 银白科技（默认方案）；想看暗色把 darkTheme 改成 true
    OpcTheme(darkTheme = false) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { content() }
    }
}

@Composable
private fun PreviewScroll(content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
    ) { content() }
}

/** 工作台：整屏流水（全部任务 + 四类动作），下面挂着输入区。 */
@Preview(name = "工作台 · 任务流水", showBackground = true, heightDp = 900)
@Composable
private fun WorkbenchPreview() {
    Phone {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
            LocalWorkbenchBar()
            OfflineBar(linkState = Demo.workbench.linkState, lastSync = Demo.workbench.lastSync)
            PreviewScroll {
                Demo.workbench.diaries.forEach { diary ->
                    DiarRow(diary)
                    Spacer(Modifier.padding(top = OpcSpacing.m))
                }
            }
        }
    }
}

/** 工作台 · 输入区展开 @ 指派行。 */
@Preview(name = "工作台 · @ 指派角色", showBackground = true, heightDp = 260)
@Composable
private fun WorkbenchMentionPreview() {
    Phone {
        Column(Modifier.fillMaxSize().padding(horizontal = OpcSpacing.s)) {
            MentionRow(roles = Demo.workbench.roles, onPick = {})
        }
    }
}

/** 总览：项目芯片 + Hero + 三指标 + 组织 + 事件。 */
@Preview(name = "总览", showBackground = true, heightDp = 1000)
@Composable
private fun OverviewPreview() {
    val state = Demo.overview
    val stats = state.stats
    Phone {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
            LocalTopBar(title = "作战面板")
            OfflineBar(linkState = state.linkState, lastSync = state.lastSync)
            if (stats == null) {
                LocalEmptyState("这屏暂时没有数据", "下拉刷新或检查服务端连接")
            } else {
                PreviewScroll {
                    LocalSectionHeader(title = "组织", meta = stats.roles.size.toString() + " ROLES")
                    LocalCard {
                        stats.roles.forEachIndexed { index, role ->
                            if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                            Text(role.code + " " + role.name + " · " + role.note, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    LocalSectionHeader(title = "实时事件", action = "工作台")
                    stats.events.forEach { Text(it.time + "  " + it.text, style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
    }
}

/** 消息：分类芯片 + 按日分组卡片流。 */
@Preview(name = "消息", showBackground = true, heightDp = 900)
@Composable
private fun MessagesPreview() {
    val state = MessagesUiState(
        loading = false,
        offline = false,
        linkState = LinkState.ONLINE,
        feed = DemoData.feed(),
    )
    Phone {
        MessagesContent(state = state, onFilter = {}, onToggle = {})
    }
}

/** 我的：连接信息 + 通知开关 + 运行开关 + 解除配对。 */
@Preview(name = "我的", showBackground = true, heightDp = 1000)
@Composable
private fun ProfilePreview() {
    val repository = remember { PreviewRepository() }
    val viewModel = remember(repository) { ProfileViewModel(repository) }
    val state = ProfileUiState(
        loading = false,
        linkState = LinkState.ONLINE,
        config = ServerConfig("192.168.1.20:8901", "preview", "DEV-7F3A-91C2", "Pixel 9 · 主人手机", "1.18.0", 0L),
        project = ProjectInfo("opc-app", "OPC-APP", 4, 3),
    )
    Phone {
        ProfileContent(state = state, viewModel = viewModel)
    }
}
