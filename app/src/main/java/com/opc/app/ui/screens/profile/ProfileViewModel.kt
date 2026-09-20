package com.opc.app.ui.screens.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.ServerConfig
import com.opc.app.ui.screens.nowHm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** 通知开关初值照 design/index.html，只有免打扰默认关。 */
internal val DefaultNotifications: Map<String, Boolean> = linkedMapOf(
    "待裁决立即推送" to true,
    "子任务完成" to true,
    "每日简报" to true,
    "执行异常 / 护栏中止" to true,
    "免打扰 23:00 - 07:00" to false,
)

data class ProfileUiState(
    val loading: Boolean = true,
    val offline: Boolean = false,
    val linkState: LinkState = LinkState.CONNECTING,
    val lastSync: String = nowHm(),
    val config: ServerConfig? = null,
    val project: ProjectInfo? = null,
    val notifications: Map<String, Boolean> = DefaultNotifications,
    val autoChain: Boolean = true,
    val offPeakQueue: Boolean = true,
    val busy: Boolean = false,
    val error: String? = null,
    val confirmUnpair: Boolean = false,
)

class ProfileViewModel(private val repository: OpcRepository) : ViewModel() {

    private val _state = MutableStateFlow(ProfileUiState())
    val state: StateFlow<ProfileUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.linkState.collect { link -> _state.value = _state.value.copy(linkState = link) }
        }
        viewModelScope.launch {
            repository.config.collect { config ->
                _state.value = _state.value.copy(config = config, autoChain = config != null)
            }
        }
        viewModelScope.launch {
            repository.project.collect { project -> _state.value = _state.value.copy(project = project) }
        }
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true)
        viewModelScope.launch {
            val result = repository.overview()
            _state.value = _state.value.copy(loading = false, offline = result.offline, lastSync = nowHm())
        }
    }

    fun toggleNotification(label: String) {
        val current = _state.value.notifications
        _state.value = _state.value.copy(notifications = current + (label to !(current[label] ?: false)))
    }

    /** 自动执行链是真远程开关，其余两个只在本机记住。 */
    fun setAutoChain(running: Boolean) {
        _state.value = _state.value.copy(autoChain = running, busy = true, error = null)
        viewModelScope.launch {
            val result = repository.pauseChain(!running)
            _state.value = _state.value.copy(
                busy = false,
                autoChain = if (result.isSuccess) running else !running,
                error = result.exceptionOrNull()?.message?.let { "服务端没接受这个开关：" + it },
            )
        }
    }

    fun setOffPeakQueue(enabled: Boolean) {
        _state.value = _state.value.copy(offPeakQueue = enabled)
    }

    fun requestUnpair() {
        _state.value = _state.value.copy(confirmUnpair = true)
    }

    fun dismissUnpair() {
        _state.value = _state.value.copy(confirmUnpair = false)
    }

    /** 解除配对后 config 变 null，根 Composable 会自动退回连接页。 */
    fun confirmUnpair() {
        _state.value = _state.value.copy(confirmUnpair = false, busy = true)
        viewModelScope.launch {
            repository.unpair()
            _state.value = _state.value.copy(busy = false)
        }
    }

    fun dismissError() {
        _state.value = _state.value.copy(error = null)
    }
}
