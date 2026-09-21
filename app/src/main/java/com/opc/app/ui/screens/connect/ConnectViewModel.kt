package com.opc.app.ui.screens.connect

import android.os.Build
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.opc.app.data.OpcRepository
import com.opc.app.data.PairFailure
import com.opc.app.data.SettingsStore
import com.opc.app.domain.PairAddress
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.QrProtocol
import com.opc.app.domain.ServerConfig
import com.opc.app.domain.TunnelProfile
import com.opc.app.domain.WireConfig
import com.opc.app.tunnel.TunnelController
import com.opc.app.tunnel.TunnelState
import com.opc.app.tunnel.TunnelUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** 预检三行的状态：还没查 / 通过 / 不通过。 */
enum class PrecheckState { UNKNOWN, PASS, FAIL }

data class ConnectUiState(
    val loading: Boolean = false,
    val address: String = "",
    val code: String = "",
    val deviceName: String = defaultDeviceName(),
    val localIpv4: String? = null,
    val sameLan: PrecheckState = PrecheckState.UNKNOWN,
    val serverOnline: PrecheckState = PrecheckState.UNKNOWN,
    val serverVersion: String? = null,
    val latencyMs: Long? = null,
    val whitelist: PrecheckState = PrecheckState.UNKNOWN,
    val checking: Boolean = false,
    val pairing: Boolean = false,
    val error: String? = null,
    val paired: ServerConfig? = null,
    val project: ProjectInfo? = null,
    val scanEnabled: Boolean = true,
    /** 二维码里的隧道骨架（老二维码为 null）。 */
    val wire: WireConfig? = null,
    /** 配对成功后落盘的隧道档案；null = 这次配对不进隧道。 */
    val tunnelProfile: TunnelProfile? = null,
    /** 非致命告警（例如设备 confirm 没走通）。 */
    val tunnelWarning: String? = null,
    val tunnel: TunnelUiState = TunnelUiState(),
)

private fun defaultDeviceName(): String =
    Build.MODEL.takeIf { it.isNotBlank() }?.let { it + " · 主人手机" } ?: "Android 设备"

/** 配对码：去掉分隔符后 6 位以上字母数字。 */
internal fun isCodeValid(code: String): Boolean = code.count { it.isLetterOrDigit() } >= 6

internal fun normalizedCode(raw: String): String =
    raw.uppercase().filter { it.isLetterOrDigit() || it == '-' }.take(12)

class ConnectViewModel(
    private val repository: OpcRepository,
    private val settingsStore: SettingsStore,
) : ViewModel() {

    private val _state = MutableStateFlow(ConnectUiState())
    val state: StateFlow<ConnectUiState> = _state.asStateFlow()

    init {
        // 配对成功后服务端会回一个默认项目，这里跟着 flow 走，页面不做二次请求。
        viewModelScope.launch {
            repository.project.collect { project -> _state.value = _state.value.copy(project = project) }
        }
        viewModelScope.launch {
            TunnelController.state.collect { tunnel -> _state.value = _state.value.copy(tunnel = tunnel) }
        }
    }

    fun setLocalIpv4(ip: String?) {
        val current = _state.value
        _state.value = current.copy(localIpv4 = ip, sameLan = sameSubnet(current.address, ip))
    }

    fun onAddressChange(value: String) {
        val current = _state.value
        _state.value = current.copy(
            address = value,
            sameLan = sameSubnet(value, current.localIpv4),
            whitelist = PrecheckState.UNKNOWN,
            error = null,
        )
    }

    fun onCodeChange(value: String) {
        _state.value = _state.value.copy(code = normalizedCode(value), whitelist = PrecheckState.UNKNOWN, error = null)
    }

    /** 扫到码：解析成功就自动跑一次预检，解析失败留在扫码页继续扫。 */
    fun onQrDecoded(raw: String) {
        val ticket = QrProtocol.parse(raw)
        if (ticket == null) {
            _state.value = _state.value.copy(error = "这不是 OPC 配对码，换服务端「连接移动端」页那张", scanEnabled = false)
            return
        }
        val current = _state.value
        _state.value = current.copy(
            address = ticket.baseUrl,
            code = normalizedCode(ticket.code),
            serverVersion = ticket.serverVersion ?: current.serverVersion,
            sameLan = sameSubnet(ticket.baseUrl, current.localIpv4),
            scanEnabled = false,
            error = null,
            wire = ticket.wire,
            tunnelWarning = null,
        )
        precheck()
    }

    fun retryScan() {
        _state.value = _state.value.copy(scanEnabled = true, error = null)
    }

    fun precheck() {
        val base = PairAddress.normalize(_state.value.address)
        if (base == null) {
            _state.value = _state.value.copy(
                serverOnline = PrecheckState.FAIL,
                latencyMs = null,
                error = "地址要写成 192.168.1.20:8901 这样",
            )
            return
        }
        _state.value = _state.value.copy(checking = true, error = null, whitelist = PrecheckState.UNKNOWN)
        viewModelScope.launch {
            val startedAt = System.currentTimeMillis()
            repository.ping(base)
                .onSuccess { version ->
                    _state.value = _state.value.copy(
                        checking = false,
                        serverOnline = PrecheckState.PASS,
                        serverVersion = version,
                        latencyMs = System.currentTimeMillis() - startedAt,
                    )
                }
                .onFailure { error ->
                    // 目标是服务端隧道地址、隧道又没起来 → 是隧道的问题，不是服务端不在线
                    val tunnelDown = isTunnelTarget(base) && _state.value.tunnel.state != TunnelState.UP
                    _state.value = _state.value.copy(
                        checking = false,
                        serverOnline = PrecheckState.FAIL,
                        latencyMs = null,
                        error = if (tunnelDown) PairFailure.TUNNEL_DOWN else error.message ?: "服务端没响应",
                    )
                }
        }
    }

    fun pair() {
        val current = _state.value
        val base = PairAddress.normalize(current.address)
        if (base == null) {
            _state.value = current.copy(error = "地址要写成 192.168.1.20:8901 这样")
            return
        }
        if (!isCodeValid(current.code)) {
            _state.value = current.copy(error = "配对码至少 6 位，大小写不敏感")
            return
        }
        _state.value = current.copy(pairing = true, error = null, whitelist = PrecheckState.UNKNOWN)
        viewModelScope.launch {
            repository.pair(base, current.code, current.deviceName, current.wire)
                .onSuccess { result ->
                    _state.value = _state.value.copy(
                        pairing = false,
                        paired = result.config,
                        whitelist = PrecheckState.PASS,
                        serverOnline = PrecheckState.PASS,
                        serverVersion = result.config.serverVersion,
                        address = result.config.baseUrl,
                        tunnelProfile = result.tunnel,
                        tunnelWarning = result.warning,
                    )
                }
                .onFailure { error ->
                    _state.value = _state.value.copy(
                        pairing = false,
                        whitelist = PrecheckState.FAIL,
                        error = error.message ?: "配对被拒绝，先确认设备白名单",
                    )
                }
        }
    }

    /** 服务端还没起时给一条能走通全部页面的路：写占位配置，根 Composable 会当作已就绪。 */
    fun enterDemoMode() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            settingsStore.enableDemoMode()
            _state.value = _state.value.copy(loading = false)
        }
    }

    fun dismissError() {
        _state.value = _state.value.copy(error = null)
    }

    /** 地址指向服务端隧道地址（档案里被隧道的那条路由，或二维码骨架里的 AllowedIPs）。 */
    private fun isTunnelTarget(baseUrl: String): Boolean {
        val host = baseUrl.substringAfter("://").substringBefore('/').substringBefore(':')
        val current = _state.value
        val serverAddress = TunnelController.profile.value?.serverAddress
            ?: current.wire?.allowedIps?.substringBefore(',')?.trim()?.substringBefore('/')
        return !serverAddress.isNullOrBlank() && serverAddress == host
    }

    private fun sameSubnet(address: String, localIpv4: String?): PrecheckState {
        if (localIpv4 == null || address.isBlank()) return PrecheckState.UNKNOWN
        val host = address.substringAfter("://").substringBefore("/").substringBefore(":")
        if (host.count { it == '.' } != 3) return PrecheckState.UNKNOWN
        return if (host.substringBeforeLast('.') == localIpv4.substringBeforeLast('.')) {
            PrecheckState.PASS
        } else {
            PrecheckState.FAIL
        }
    }
}
