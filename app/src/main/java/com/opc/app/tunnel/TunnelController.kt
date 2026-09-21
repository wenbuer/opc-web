package com.opc.app.tunnel

import android.content.Context
import android.content.Intent
import android.net.VpnService
import androidx.core.content.ContextCompat
import com.opc.app.data.SettingsStore
import com.opc.app.domain.TunnelProfile
import com.wireguard.android.backend.BackendException
import com.wireguard.android.backend.GoBackend
import com.wireguard.android.backend.Tunnel
import com.wireguard.config.Config
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.StringReader
import java.util.concurrent.TimeUnit

/**
 * 隧道门面：UI 只跟它打交道。
 *
 * 启停路径：
 *   配对成功 → VpnService.prepare 拿授权 → start(profile)
 *     → 前台 VpnService 起来（OpcTunnelService）→ GoBackend.setState(UP, Config)
 *     → 库里按 AllowedIPs 建路由（只有服务端隧道地址 /32）并拉起 wg
 *   断开 → GoBackend.setState(DOWN) → 库自己 stopSelf，前台通知随之撤掉
 *
 * 进程内单例：App 启动时 install 一次；预览环境不 install，状态停在 IDLE，不会弹任何授权。
 */
object TunnelController {

    private const val TUNNEL_NAME = "opc"
    private const val SERVICE_START_TIMEOUT_MS = 3000L

    private val _state = MutableStateFlow(TunnelUiState())
    val state: StateFlow<TunnelUiState> = _state.asStateFlow()

    /** 已落盘的隧道档案；没有 = 不进隧道（老二维码 / 演示模式）。 */
    private val _profile = MutableStateFlow<TunnelProfile?>(null)
    val profile: StateFlow<TunnelProfile?> = _profile.asStateFlow()

    val lastError: String? get() = _state.value.lastError

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var appContext: Context? = null
    private var backend: GoBackend? = null
    private var job: Job? = null

    private val tunnel = object : Tunnel {
        override fun getName(): String = TUNNEL_NAME

        override fun onStateChange(newState: Tunnel.State) {
            _state.value = _state.value.reduce(
                if (newState == Tunnel.State.UP) TunnelEvent.Up else TunnelEvent.Down,
            )
        }
    }

    fun install(context: Context, store: SettingsStore) {
        appContext = context.applicationContext
        scope.launch { store.tunnelProfile.collect { _profile.value = it } }
    }

    /** 需要授权时返回系统 VPN 授权 Intent；返回 null = 已授权或环境未就绪。 */
    fun prepareIntent(): Intent? {
        val context = appContext ?: return null
        return runCatching { VpnService.prepare(context) }.getOrNull()
    }

    fun start(profile: TunnelProfile) {
        if (_state.value.state == TunnelState.CONNECTING) return
        _state.value = _state.value.reduce(TunnelEvent.StartRequested)
        job?.cancel()
        job = scope.launch {
            val outcome = runCatching { bringUp(profile) }
            _state.value = _state.value.reduce(
                outcome.fold(
                    onSuccess = { TunnelEvent.Up },
                    onFailure = { TunnelEvent.Failed(friendlyMessage(it)) },
                ),
            )
        }
    }

    fun stop() {
        job?.cancel()
        scope.launch {
            runCatching { backend?.setState(tunnel, Tunnel.State.DOWN, null) }
            _state.value = _state.value.reduce(TunnelEvent.Down)
        }
    }

    fun reconnect() {
        val profile = _profile.value
        if (profile == null) {
            // 没配隧道（老二维码 / 演示模式）不是「连接失败」，就是没这东西：停在未连接
            _state.value = _state.value.reduce(TunnelEvent.Down)
            return
        }
        start(profile)
    }

    /** 冷启动：只在「已授权」时静默恢复，绝不擅自弹授权框（演示模式尤其不能弹）。 */
    fun startIfAuthorized() {
        val profile = _profile.value ?: return
        val current = _state.value.state
        if (current == TunnelState.UP || current == TunnelState.CONNECTING) return
        if (prepareIntent() != null) return
        start(profile)
    }

    fun onPermissionDenied() {
        _state.value = _state.value.reduce(TunnelEvent.Failed("VPN 授权被拒绝，隧道未建立"))
    }

    // ---------- 内部 ----------

    private fun bringUp(profile: TunnelProfile) {
        val context = requireNotNull(appContext) { "隧道未初始化" }
        if (prepareIntent() != null) throw BackendException(BackendException.Reason.VPN_NOT_AUTHORIZED)
        val config = Config.parse(StringReader(WireGuardConfig.toWgQuickText(profile)).buffered())
        val signal = OpcTunnelService.expectStart()
        ContextCompat.startForegroundService(context, OpcTunnelService.startIntent(context))
        // 必须等前台服务把实例登记进 GoBackend，否则库会去启动它自带的那个声明（已被移除）；
        // 等不到就在超时处抛，转成 ERROR 状态
        signal.get(SERVICE_START_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        engine(context).setState(tunnel, Tunnel.State.UP, config)
    }

    private fun engine(context: Context): GoBackend = backend ?: synchronized(this) {
        backend ?: GoBackend(context).also { backend = it }
    }

    private fun friendlyMessage(error: Throwable): String = when {
        error is BackendException -> when (error.reason) {
            BackendException.Reason.VPN_NOT_AUTHORIZED -> "系统未授权 VPN，隧道没建起来"
            BackendException.Reason.UNABLE_TO_START_VPN -> "隧道服务起不来"
            BackendException.Reason.TUN_CREATION_ERROR -> "系统拒绝建立隧道"
            BackendException.Reason.TUNNEL_MISSING_CONFIG -> "隧道配置不完整"
            BackendException.Reason.DNS_RESOLUTION_FAILURE -> "endpoint 域名解析失败"
            BackendException.Reason.GO_ACTIVATION_ERROR_CODE -> "WireGuard 后端启动失败"
            else -> "建立隧道失败"
        }
        else -> error.message ?: "建立隧道失败"
    }
}
