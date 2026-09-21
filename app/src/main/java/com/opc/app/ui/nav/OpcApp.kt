package com.opc.app.ui.nav

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarDefaults
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.opc.app.OpcApplication
import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.ui.OpcViewModelFactory
import com.opc.app.ui.theme.silverBackgroundBrush
import com.opc.app.ui.theme.techGrid
import com.opc.app.ui.screens.connect.ConnectScreen
import com.opc.app.ui.screens.messages.MessagesScreen
import com.opc.app.ui.screens.overview.OverviewScreen
import com.opc.app.ui.screens.profile.ProfileScreen
import com.opc.app.ui.screens.review.ReviewScreen
import com.opc.app.ui.screens.workbench.WorkbenchScreen

/**
 * 根 Composable：未配对只给连接页，配对后才挂底栏与 NavHost。
 * 主题在 MainActivity 里已经套过一层，这里不再重复 OpcTheme。
 */
@Composable
fun OpcApp() {
    val context = LocalContext.current
    val container = (context.applicationContext as OpcApplication).container
    val repository = container.repository
    val factory: ViewModelProvider.Factory = remember(repository) {
        OpcViewModelFactory(repository, container.settingsStore)
    }

    val config by repository.config.collectAsState(initial = null)
    // 刚配对成功时要先让用户看完配对回执卡，点「进入作战面板」才切主界面；
    // 冷启动就已配对的情况不走这条分支（justPaired 初值为 false）。
    var justPaired by rememberSaveable { mutableStateOf(false) }

    if (config == null || justPaired) {
        ConnectScreen(
            factory = factory,
            onPaired = { justPaired = true },
            onEnter = { justPaired = false },
        )
    } else {
        MainScaffold(repository = repository, factory = factory)
    }
}

@Composable
private fun MainScaffold(repository: OpcRepository, factory: ViewModelProvider.Factory) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route ?: OpcDestination.OVERVIEW.route
    val linkState by repository.linkState.collectAsState(initial = LinkState.CONNECTING)

    // 底栏徽标：批阅台 = 待裁决数，工作台 = 未读消息数。只拉一次，切页不重复请求。
    var reviewBadge by remember { mutableStateOf(0) }
    var workbenchBadge by remember { mutableStateOf(0) }
    LaunchedEffect(linkState) {
        reviewBadge = runCatching { repository.overview().data.pendingReview }.getOrDefault(0)
        workbenchBadge = runCatching { repository.feed().data.count { !it.read } }.getOrDefault(0)
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        // 顶部不做 Scaffold 内缩：每个页面自己用 StatusBarSpacer 贴状态栏，
        // 两处都缩会多出一段空白（就是之前标题下面那一块）。
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surfaceContainer,
                windowInsets = NavigationBarDefaults.windowInsets,
            ) {
                OpcDestination.entries.forEach { destination ->
                    val selected = currentRoute == destination.route
                    val count = when (destination) {
                        OpcDestination.WORKBENCH -> workbenchBadge
                        OpcDestination.REVIEW -> reviewBadge
                        else -> 0
                    }
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            if (!selected) {
                                navController.navigate(destination.route) {
                                    launchSingleTop = true
                                    restoreState = true
                                    popUpTo(navController.graph.startDestinationId) { saveState = true }
                                }
                            }
                        },
                        icon = {
                            Box(
                                modifier = Modifier
                                    .size(54.dp, 32.dp)
                                    .clip(CircleShape)
                                    .background(
                                        if (selected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                                    ),
                                contentAlignment = Alignment.Center,
                            ) {
                                val tint = if (selected) {
                                    MaterialTheme.colorScheme.primary
                                } else {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                }
                                if (count > 0) {
                                    BadgedBox(badge = { Badge { Text(count.toString()) } }) {
                                        Icon(destination.icon, contentDescription = destination.label, tint = tint, modifier = Modifier.size(21.dp))
                                    }
                                } else {
                                    Icon(destination.icon, contentDescription = destination.label, tint = tint, modifier = Modifier.size(21.dp))
                                }
                            }
                        },
                        label = { Text(destination.label, style = MaterialTheme.typography.labelSmall) },
                        colors = NavigationBarItemDefaults.colors(
                            indicatorColor = Color.Transparent,
                            selectedTextColor = MaterialTheme.colorScheme.onSurface,
                            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        ),
                    )
                }
            }
        },
    ) { innerPadding ->
        // 银白科技底：竖向渐变（金属受光面）+ 细网格。只在这里画一次，
        // 各页只管内容；页面自己再刷一层纯色底会把网格盖掉。
        Box(
            Modifier
                .fillMaxSize()
                .background(silverBackgroundBrush())
                .techGrid()
                .padding(innerPadding),
        ) {
        NavHost(
            navController = navController,
            startDestination = OpcDestination.OVERVIEW.route,
            modifier = Modifier.fillMaxSize(),
        ) {
            composable(OpcDestination.OVERVIEW.route) { OverviewScreen(factory) }
            composable(OpcDestination.WORKBENCH.route) { WorkbenchScreen(factory) }
            composable(OpcDestination.REVIEW.route) { ReviewScreen(factory) }
            composable(OpcDestination.MESSAGES.route) { MessagesScreen(factory) }
            composable(OpcDestination.PROFILE.route) { ProfileScreen(factory) }
        }
        }
    }
}
