package com.opc.app.ui.screens.connect

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.journeyapps.barcodescanner.BarcodeCallback
import com.journeyapps.barcodescanner.BarcodeResult
import com.journeyapps.barcodescanner.DecoratedBarcodeView
import com.journeyapps.barcodescanner.DefaultDecoderFactory
import com.google.zxing.BarcodeFormat
import com.google.zxing.ResultPoint
import com.opc.app.ui.components.CapsuleChip
import com.opc.app.ui.components.GhostChip
import com.opc.app.ui.components.HeroCard
import com.opc.app.ui.components.StatusBarSpacer
import com.opc.app.ui.components.TierTag
import com.opc.app.ui.components.TierTone
import com.opc.app.ui.screens.LocalCard
import com.opc.app.ui.screens.LocalKeyValueRow
import com.opc.app.ui.screens.LocalSectionHeader
import com.opc.app.tunnel.TunnelController
import com.opc.app.tunnel.TunnelState
import com.opc.app.tunnel.TunnelUiState
import com.opc.app.ui.theme.OpcGold
import com.opc.app.ui.theme.silverBackgroundBrush
import com.opc.app.ui.theme.techGrid
import com.opc.app.ui.theme.OpcGreen
import com.opc.app.ui.theme.OpcRed
import com.opc.app.ui.theme.OpcScreenPadding
import com.opc.app.ui.theme.OpcSpacing

private val ScannerBackground = Color(0xFF0F1116)

@Composable
fun ConnectScreen(
    factory: ViewModelProvider.Factory,
    onPaired: () -> Unit,
    onEnter: () -> Unit,
) {
    val viewModel: ConnectViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    var cameraGranted by remember { mutableStateOf(context.hasCameraPermission()) }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        cameraGranted = granted
    }

    LaunchedEffect(Unit) {
        viewModel.setLocalIpv4(context.localIpv4())
        if (!context.hasCameraPermission()) permissionLauncher.launch(Manifest.permission.CAMERA)
    }
    LaunchedEffect(state.paired) {
        if (state.paired != null) onPaired()
    }

    // VPN 授权只能在 Activity 里要：配对成功拿到隧道档案后弹一次，被拒绝可重试
    val latestProfile by rememberUpdatedState(state.tunnelProfile)
    val vpnLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val profile = latestProfile
        if (result.resultCode == Activity.RESULT_OK && profile != null) {
            TunnelController.start(profile)
        } else {
            TunnelController.onPermissionDenied()
        }
    }
    val requestTunnel: () -> Unit = {
        val profile = state.tunnelProfile
        if (profile != null) {
            val intent = TunnelController.prepareIntent()
            if (intent == null) TunnelController.start(profile) else vpnLauncher.launch(intent)
        }
    }
    LaunchedEffect(state.tunnelProfile) {
        if (state.tunnelProfile != null) requestTunnel()
    }

    // 连接页在 Scaffold 之外（未配对时没有底栏），底纹自己补一份，和主界面同底
    Box(Modifier.fillMaxSize().background(silverBackgroundBrush()).techGrid()) {
        if (state.paired != null) {
            PairSuccessPanel(state = state, onEnter = onEnter, onRetryTunnel = requestTunnel)
        } else {
            Column(Modifier.fillMaxSize()) {
                StatusBarSpacer()
                ScannerPane(
                    cameraGranted = cameraGranted,
                    scanEnabled = state.scanEnabled,
                    onDecoded = viewModel::onQrDecoded,
                    onRequestPermission = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                    onRetryScan = viewModel::retryScan,
                )
                Column(
                    Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = OpcScreenPadding),
                ) {
                    ManualPanel(state = state, viewModel = viewModel)
                }
                BottomActions(
                    pairing = state.pairing,
                    onPair = viewModel::pair,
                    onDemo = viewModel::enterDemoMode,
                )
            }
        }
    }
}

/* ---------------- 取景区 ---------------- */

@Composable
private fun ScannerPane(
    cameraGranted: Boolean,
    scanEnabled: Boolean,
    onDecoded: (String) -> Unit,
    onRequestPermission: () -> Unit,
    onRetryScan: () -> Unit,
) {
    val latestDecode by rememberUpdatedState(onDecoded)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(262.dp)
            .background(ScannerBackground),
    ) {
        if (cameraGranted && scanEnabled) {
            var scanner by remember { mutableStateOf<DecoratedBarcodeView?>(null) }
            DisposableEffect(Unit) { onDispose { scanner?.pause() } }
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    DecoratedBarcodeView(ctx).apply {
                        scanner = this
                        barcodeView.decoderFactory = DefaultDecoderFactory(listOf(BarcodeFormat.QR_CODE))
                        barcodeView.cameraSettings.isContinuousFocusEnabled = true
                        setStatusText("")
                        decodeContinuous(object : BarcodeCallback {
                            override fun barcodeResult(result: BarcodeResult) {
                                result.text?.let { latestDecode(it) }
                            }

                            override fun possibleResultPoints(resultPoints: MutableList<ResultPoint>) = Unit
                        })
                    }
                },
            )
        } else {
            Column(
                modifier = Modifier.fillMaxSize().padding(horizontal = OpcSpacing.xl),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = if (cameraGranted) "已暂停扫描，可继续手填" else "没有相机权限，用下面的地址和配对码接入",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFFC9CFFE),
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(OpcSpacing.m))
                if (cameraGranted) {
                    CapsuleChip(text = "重新扫描", onClick = onRetryScan)
                } else {
                    CapsuleChip(text = "授权相机", onClick = onRequestPermission)
                }
            }
        }

        ScanFrameOverlay(Modifier.align(Alignment.Center))

        Row(
            modifier = Modifier
                .align(Alignment.TopStart)
                .fillMaxWidth()
                .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m),
        ) {
            Icon(Icons.Default.Info, contentDescription = null, tint = Color(0xFFE6ECF7), modifier = Modifier.size(18.dp))
            Text("扫描配对二维码", style = MaterialTheme.typography.titleSmall, color = Color(0xFFE6ECF7))
        }

        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "对准服务端「连接移动端」页面的二维码",
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFFC9CFFE),
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = "当前网段 " + (subnetOf(LocalContext.current) ?: "未识别") + " · 已发现服务端 1 台",
                style = MaterialTheme.typography.labelSmall,
                color = Color(0xFF9AA3B2),
            )
        }
    }
}

@Composable
private fun ScanFrameOverlay(modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "laser")
    val fraction by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(2600, easing = LinearEasing), RepeatMode.Reverse),
        label = "laserY",
    )
    Box(modifier.size(212.dp)) {
        Box(Modifier.matchParentSize().cornerMark(Corner.TOP_START, OpcGold))
        Box(Modifier.matchParentSize().cornerMark(Corner.TOP_END, OpcGold))
        Box(Modifier.matchParentSize().cornerMark(Corner.BOTTOM_START, OpcGold))
        Box(Modifier.matchParentSize().cornerMark(Corner.BOTTOM_END, OpcGold))
        Box(
            Modifier
                .fillMaxWidth()
                .offset(y = 200.dp * fraction)
                .height(2.dp)
                .background(Brush.horizontalGradient(listOf(Color.Transparent, OpcGold, Color.Transparent))),
        )
    }
}

private enum class Corner { TOP_START, TOP_END, BOTTOM_START, BOTTOM_END }

/** 四角描边：两条矩形拼出 L 形，比画布 clip 省事。 */
private fun Modifier.cornerMark(corner: Corner, color: Color): Modifier = drawBehind {
    val length = 34.dp.toPx()
    val thickness = 3.dp.toPx()
    val horizontal = Size(length, thickness)
    val vertical = Size(thickness, length)
    when (corner) {
        Corner.TOP_START -> {
            drawRect(color, Offset.Zero, horizontal)
            drawRect(color, Offset.Zero, vertical)
        }
        Corner.TOP_END -> {
            drawRect(color, Offset(size.width - length, 0f), horizontal)
            drawRect(color, Offset(size.width - thickness, 0f), vertical)
        }
        Corner.BOTTOM_START -> {
            drawRect(color, Offset(0f, size.height - thickness), horizontal)
            drawRect(color, Offset(0f, size.height - length), vertical)
        }
        Corner.BOTTOM_END -> {
            drawRect(color, Offset(size.width - length, size.height - thickness), horizontal)
            drawRect(color, Offset(size.width - thickness, size.height - length), vertical)
        }
    }
}

/* ---------------- 手动接入 ---------------- */

@Composable
private fun ManualPanel(state: ConnectUiState, viewModel: ConnectViewModel) {
    Spacer(Modifier.height(OpcSpacing.m))
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
        Text("手动接入", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
        if (state.checking) {
            CircularProgressIndicator(Modifier.size(13.dp), strokeWidth = 2.dp)
        }
        Spacer(Modifier.weight(1f))
        if (state.serverVersion != null) {
            GhostChip(text = "opc-web v" + state.serverVersion, leadingDot = true)
        }
    }
    Spacer(Modifier.height(OpcSpacing.m))

    OutlinedTextField(
        value = state.address,
        onValueChange = viewModel::onAddressChange,
        label = { Text("服务端地址") },
        placeholder = { Text("192.168.1.20:8901") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(OpcSpacing.m))
    val codeSupport: @Composable (() -> Unit)? =
        if (state.code.isNotEmpty() && !isCodeValid(state.code)) {
            { Text("配对码至少 6 位") }
        } else {
            null
        }
    OutlinedTextField(
        value = state.code,
        onValueChange = viewModel::onCodeChange,
        label = { Text("配对码") },
        placeholder = { Text("K7QP-3M2X") },
        singleLine = true,
        supportingText = codeSupport,
        modifier = Modifier.fillMaxWidth(),
    )

    LocalSectionHeader(title = "连接前预检", meta = "3 项")
    LocalCard {
        PrecheckRow("同一局域网", state.sameLan, detail = null)
        PrecheckRow("服务端在线", state.serverOnline, detail = state.latencyMs?.let { "8901 已响应 " + it + "ms" })
        PrecheckRow("设备白名单", state.whitelist, detail = null)
    }

    if (state.error != null) {
        Spacer(Modifier.height(OpcSpacing.m))
        LocalCard(background = MaterialTheme.colorScheme.errorContainer) {
            Row(horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
                Icon(Icons.Default.Warning, contentDescription = null, tint = OpcRed, modifier = Modifier.size(18.dp))
                Text(state.error, style = MaterialTheme.typography.bodySmall, color = OpcRed)
            }
        }
    }

    Spacer(Modifier.height(OpcSpacing.m))
    LocalCard(background = MaterialTheme.colorScheme.errorContainer) {
        Row(horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s)) {
            Icon(Icons.Default.Info, contentDescription = null, tint = OpcRed, modifier = Modifier.size(18.dp))
            Text(
                text = "服务端默认只监听 127.0.0.1。需在服务端「设置 -> 移动端接入」开启局域网监听并放行本设备，否则连接会被拒绝。",
                style = MaterialTheme.typography.bodySmall,
                color = OpcRed,
            )
        }
    }
    Spacer(Modifier.height(OpcSpacing.l))
}

@Composable
private fun PrecheckRow(label: String, status: PrecheckState, detail: String?) {
    val scheme = MaterialTheme.colorScheme
    val (icon, color) = when (status) {
        PrecheckState.PASS -> Icons.Default.Check to OpcGreen
        PrecheckState.FAIL -> Icons.Default.Close to OpcRed
        PrecheckState.UNKNOWN -> Icons.Default.Info to scheme.onSurfaceVariant
    }
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m),
    ) {
        Box(
            Modifier.size(26.dp).clip(RoundedCornerShape(8.dp)).background(color.copy(alpha = 0.16f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(15.dp))
        }
        Text(label, style = MaterialTheme.typography.bodyMedium, color = scheme.onSurface, modifier = Modifier.weight(1f))
        Text(
            text = detail ?: when (status) {
                PrecheckState.PASS -> "通过"
                PrecheckState.FAIL -> "未通过"
                PrecheckState.UNKNOWN -> "待检"
            },
            style = MaterialTheme.typography.labelMedium,
            color = if (status == PrecheckState.UNKNOWN) scheme.onSurfaceVariant else color,
        )
    }
}

/* ---------------- 底部按钮 ---------------- */

@Composable
private fun BottomActions(pairing: Boolean, onPair: () -> Unit, onDemo: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .navigationBarsPadding()
            .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
    ) {
        Button(
            onClick = onPair,
            enabled = !pairing,
            modifier = Modifier.fillMaxWidth().height(44.dp),
        ) {
            if (pairing) {
                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(OpcSpacing.s))
            }
            Text("配对并连接")
        }
        TextButton(onClick = onDemo, modifier = Modifier.fillMaxWidth()) {
            Text("服务端还没起？先进演示模式", style = MaterialTheme.typography.labelMedium)
        }
    }
}

/* ---------------- 配对成功 ---------------- */

@Composable
private fun PairSuccessPanel(state: ConnectUiState, onEnter: () -> Unit, onRetryTunnel: () -> Unit) {
    val config = state.paired ?: return
    Column(Modifier.fillMaxSize()) {
        StatusBarSpacer()
        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = OpcScreenPadding),
        ) {
            Spacer(Modifier.height(OpcSpacing.m))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.l)) {
                Box(
                    Modifier.size(54.dp).clip(RoundedCornerShape(18.dp))
                        .background(MaterialTheme.colorScheme.tertiaryContainer),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Default.Check, contentDescription = null, tint = OpcGreen, modifier = Modifier.size(28.dp))
                }
                Column {
                    Text("已连接到服务端", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurface)
                    Text(
                        "设备令牌已下发，本机加入白名单",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 3.dp),
                    )
                }
            }

            Spacer(Modifier.height(OpcSpacing.l))
            HeroCard(
                title = "设备码 " + config.deviceCode,
                subtitle = "服务端 opc-web v" + config.serverVersion,
                trailing = "长期",
            ) {
                LocalKeyValueRow("服务端", config.baseUrl)
                LocalKeyValueRow("设备名", config.deviceName)
                LocalKeyValueRow(
                    key = "当前项目",
                    value = state.project?.name ?: "未选择",
                    valueColor = MaterialTheme.colorScheme.primary,
                )
            }

            LocalSectionHeader(title = "选择进入的项目", meta = "1 个可用")
            LocalCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(OpcSpacing.m)) {
                    Box(
                        Modifier.size(38.dp).clip(RoundedCornerShape(12.dp))
                            .background(MaterialTheme.colorScheme.primaryContainer),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Check, contentDescription = null, tint = OpcGold, modifier = Modifier.size(17.dp))
                    }
                    Column(Modifier.weight(1f)) {
                        Text(
                            state.project?.name ?: "OPC-APP",
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        Text(
                            text = projectNote(state),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TierTag("当前", TierTone.R1)
                }
            }

            TunnelPanel(state = state, onRetry = onRetryTunnel)

            Spacer(Modifier.height(OpcSpacing.m))
            LocalCard(background = MaterialTheme.colorScheme.surfaceContainerHigh) {
                Text(
                    "令牌仅存于本机安全存储，App 只用它换取一次性会话；可在服务端随时吊销该设备。",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(OpcSpacing.l))
        }
        Column(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .navigationBarsPadding()
                .padding(horizontal = OpcScreenPadding, vertical = OpcSpacing.m),
        ) {
            Button(onClick = onEnter, modifier = Modifier.fillMaxWidth().height(44.dp)) {
                Text("进入作战面板")
            }
        }
    }
}

/* ---------------- 内嵌隧道 ---------------- */

/** 配对回执里的隧道一块：状态、地址、endpoint、模式，失败可原地重试授权。 */
@Composable
private fun TunnelPanel(state: ConnectUiState, onRetry: () -> Unit) {
    val profile = state.tunnelProfile
    LocalSectionHeader(title = "内嵌隧道", meta = if (profile == null) "未启用" else "WireGuard")
    LocalCard {
        if (profile == null) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Default.Info,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(18.dp),
                )
                Text(
                    "这次配对没有隧道参数（老二维码或服务端未下发），App 直连服务端地址。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            TunnelStatusRow(state = state.tunnel, onRetry = onRetry)
            LocalKeyValueRow("服务端隧道地址", profile.serverAddress)
            LocalKeyValueRow("endpoint", profile.endpoint)
            LocalKeyValueRow("模式", profile.mode.label)
        }
        state.tunnelWarning?.let { warning ->
            Text(
                text = warning,
                style = MaterialTheme.typography.labelSmall,
                color = OpcRed,
                modifier = Modifier.padding(top = OpcSpacing.s),
            )
        }
    }
}

/** 状态行：图标 + 中文状态 + 失败原因；未连上时给一个原地重试。 */
@Composable
private fun TunnelStatusRow(state: TunnelUiState, onRetry: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val (icon, tint) = when (state.state) {
        TunnelState.UP -> Icons.Default.Check to OpcGreen
        TunnelState.CONNECTING -> Icons.Default.Refresh to OpcGold
        TunnelState.ERROR -> Icons.Default.Warning to OpcRed
        TunnelState.DOWN, TunnelState.IDLE -> Icons.Default.Info to scheme.onSurfaceVariant
    }
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OpcSpacing.s),
    ) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
        Column(Modifier.weight(1f)) {
            Text(
                "隧道 " + state.label,
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurface,
            )
            state.lastError?.let { message ->
                Text(message, style = MaterialTheme.typography.labelSmall, color = OpcRed)
            }
        }
        if (state.state == TunnelState.ERROR || state.state == TunnelState.DOWN || state.state == TunnelState.IDLE) {
            TextButton(onClick = onRetry) { Text("重试", style = MaterialTheme.typography.labelMedium) }
        }
    }
}

private fun projectNote(state: ConnectUiState): String {
    val project = state.project ?: return "4 角色 · 进行中 3 子任务"
    return project.roleCount.toString() + " 角色 · 进行中 " + project.runningSubtasks + " 子任务"
}

/* ---------------- 本机网络信息 ---------------- */

private fun Context.hasCameraPermission(): Boolean =
    ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

private fun Context.localIpv4(): String? = runCatching {
    java.net.NetworkInterface.getNetworkInterfaces().toList()
        .filter { it.isUp && !it.isLoopback }
        .flatMap { it.inetAddresses.toList() }
        .filterIsInstance<java.net.Inet4Address>()
        .firstOrNull { it.isSiteLocalAddress }
        ?.hostAddress
}.getOrNull()

private fun subnetOf(context: Context): String? =
    context.localIpv4()?.substringBeforeLast('.')?.let { it + ".0/24" }
