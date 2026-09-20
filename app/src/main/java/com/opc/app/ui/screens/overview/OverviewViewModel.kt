package com.opc.app.ui.screens.overview

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.domain.OverviewStats
import com.opc.app.domain.ProjectInfo
import com.opc.app.ui.screens.nowHm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class OverviewUiState(
    val loading: Boolean = true,
    val offline: Boolean = false,
    val linkState: LinkState = LinkState.CONNECTING,
    val lastSync: String = nowHm(),
    val project: ProjectInfo? = null,
    val host: String? = null,
    val stats: OverviewStats? = null,
    val error: String? = null,
)

class OverviewViewModel(private val repository: OpcRepository) : ViewModel() {

    private val _state = MutableStateFlow(OverviewUiState())
    val state: StateFlow<OverviewUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.linkState.collect { link -> _state.value = _state.value.copy(linkState = link) }
        }
        viewModelScope.launch {
            repository.project.collect { project -> _state.value = _state.value.copy(project = project) }
        }
        viewModelScope.launch {
            repository.config.collect { config ->
                _state.value = _state.value.copy(host = config?.baseUrl?.substringAfter("://"))
            }
        }
        refresh()
    }

    /** 顶栏刷新按钮与首次加载走同一条路，不另做下拉刷新。 */
    fun refresh() {
        _state.value = _state.value.copy(loading = true)
        viewModelScope.launch {
            val result = repository.overview()
            _state.value = _state.value.copy(
                loading = false,
                offline = result.offline,
                lastSync = nowHm(),
                stats = result.data,
                error = result.error,
            )
        }
    }
}
