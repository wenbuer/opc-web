package com.opc.app.ui.screens.review

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.domain.PendingItem
import com.opc.app.domain.TaskSummary
import com.opc.app.domain.Verdict
import com.opc.app.ui.screens.nowHm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ReviewUiState(
    val loading: Boolean = true,
    val offline: Boolean = false,
    val linkState: LinkState = LinkState.CONNECTING,
    val lastSync: String = nowHm(),
    val pending: List<PendingItem> = emptyList(),
    val tasks: List<TaskSummary> = emptyList(),
    val choices: Map<String, Int> = emptyMap(),
    val submitting: Boolean = false,
    val error: String? = null,
)

internal fun pendingKey(item: PendingItem): String = item.taskNo + "-" + item.subNo

class ReviewViewModel(private val repository: OpcRepository) : ViewModel() {

    private val _state = MutableStateFlow(ReviewUiState())
    val state: StateFlow<ReviewUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.linkState.collect { link -> _state.value = _state.value.copy(linkState = link) }
        }
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true)
        viewModelScope.launch {
            val pending = repository.pending()
            val tasks = repository.tasks()
            _state.value = _state.value.copy(
                loading = false,
                offline = pending.offline || tasks.offline,
                lastSync = nowHm(),
                pending = pending.data,
                tasks = tasks.data,
            )
        }
    }

    fun choose(key: String, index: Int) {
        _state.value = _state.value.copy(choices = _state.value.choices + (key to index))
    }

    /** 吸底三键只对列表第一项生效：待裁决永远按等待时长排在最前。 */
    fun submit(verdict: Verdict, opinion: String) {
        val item = _state.value.pending.firstOrNull() ?: return
        _state.value = _state.value.copy(submitting = true, error = null)
        viewModelScope.launch {
            repository.verdict(item.taskNo, item.subNo, verdict, opinion).onSuccess {
                _state.value = _state.value.copy(
                    submitting = false,
                    pending = _state.value.pending.filterNot { pendingKey(it) == pendingKey(item) },
                )
            }.onFailure { error ->
                _state.value = _state.value.copy(submitting = false, error = error.message ?: "裁决没送出去")
            }
        }
    }

    fun dismissError() {
        _state.value = _state.value.copy(error = null)
    }
}
