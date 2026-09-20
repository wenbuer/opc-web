package com.opc.app.ui.screens.workbench

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.domain.ChatItem
import com.opc.app.ui.screens.nowHm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class WorkbenchUiState(
    val loading: Boolean = true,
    val offline: Boolean = false,
    val linkState: LinkState = LinkState.CONNECTING,
    val lastSync: String = nowHm(),
    val members: List<String> = emptyList(),
    val items: List<ChatItem> = emptyList(),
    val draft: String = "",
    val sending: Boolean = false,
    val error: String? = null,
)

class WorkbenchViewModel(private val repository: OpcRepository) : ViewModel() {

    private val _state = MutableStateFlow(WorkbenchUiState())
    val state: StateFlow<WorkbenchUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.linkState.collect { link -> _state.value = _state.value.copy(linkState = link) }
        }
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true)
        viewModelScope.launch {
            val result = repository.chat()
            val members = result.data.filterIsInstance<ChatItem.Agent>().map { it.avatar }.distinct()
            _state.value = _state.value.copy(
                loading = false,
                offline = result.offline,
                lastSync = nowHm(),
                items = result.data,
                members = members,
            )
        }
    }

    fun onDraftChange(value: String) {
        _state.value = _state.value.copy(draft = value)
    }

    /** 三个快捷芯片只是把意图写进输入框，不直接发送——发什么话仍由人过一眼。 */
    fun applyQuickIntent(prefix: String) {
        _state.value = _state.value.copy(draft = prefix)
    }

    fun send() {
        val text = _state.value.draft.trim()
        if (text.isEmpty()) return
        val mine = ChatItem.Mine(id = "local-" + System.currentTimeMillis(), text = text, time = nowHm())
        _state.value = _state.value.copy(
            items = _state.value.items + mine,
            draft = "",
            sending = true,
            error = null,
        )
        viewModelScope.launch {
            val result = repository.dispatch(text)
            _state.value = _state.value.copy(
                sending = false,
                error = result.exceptionOrNull()?.message?.let { "下达失败：" + it },
            )
        }
    }
}
