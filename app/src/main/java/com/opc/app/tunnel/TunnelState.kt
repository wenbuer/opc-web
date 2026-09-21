package com.opc.app.tunnel

/** 隧道状态。CONNECTING 是「已发起、尚未建立」，DOWN 与 IDLE 对用户都是「未连接」。 */
enum class TunnelState { IDLE, CONNECTING, UP, DOWN, ERROR }

sealed interface TunnelEvent {
    data object StartRequested : TunnelEvent
    data object Up : TunnelEvent
    data object Down : TunnelEvent
    data class Failed(val message: String) : TunnelEvent
}

data class TunnelUiState(
    val state: TunnelState = TunnelState.IDLE,
    val lastError: String? = null,
) {
    val connected: Boolean get() = state == TunnelState.UP

    /** 状态芯片与「我的」区块共用的中文标签。 */
    val label: String
        get() = when (state) {
            TunnelState.UP -> "已连接"
            TunnelState.CONNECTING -> "连接中"
            TunnelState.ERROR -> "连接失败"
            TunnelState.DOWN, TunnelState.IDLE -> "未连接"
        }
}

/**
 * 纯迁移函数：不碰 Android，单测直接喂事件序列。
 * 失败一律收敛到 ERROR 并保留原因；重新发起从 ERROR 回到 CONNECTING。
 */
fun TunnelUiState.reduce(event: TunnelEvent): TunnelUiState = when (event) {
    TunnelEvent.StartRequested -> TunnelUiState(TunnelState.CONNECTING, null)
    TunnelEvent.Up -> TunnelUiState(TunnelState.UP, null)
    TunnelEvent.Down -> TunnelUiState(TunnelState.DOWN, null)
    is TunnelEvent.Failed -> TunnelUiState(TunnelState.ERROR, event.message)
}
