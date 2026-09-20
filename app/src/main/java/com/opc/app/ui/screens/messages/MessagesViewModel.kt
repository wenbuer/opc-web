package com.opc.app.ui.screens.messages

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.domain.FeedItem
import com.opc.app.domain.FeedType
import com.opc.app.ui.screens.nowHm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** 分类芯片：系统 = 告警 + 定时，两者都是「机器自己发出来的」。 */
enum class FeedFilter(val label: String) {
    ALL("全部"),
    DAILY("简报"),
    OUTPUT("产出"),
    KNOWLEDGE("知识库"),
    SYSTEM("系统"),
}

internal fun FeedFilter.accepts(type: FeedType): Boolean = when (this) {
    FeedFilter.ALL -> true
    FeedFilter.DAILY -> type == FeedType.DAILY
    FeedFilter.OUTPUT -> type == FeedType.OUTPUT
    FeedFilter.KNOWLEDGE -> type == FeedType.KNOWLEDGE
    FeedFilter.SYSTEM -> type == FeedType.ALERT || type == FeedType.SCHEDULE
}

data class MessagesUiState(
    val loading: Boolean = true,
    val offline: Boolean = false,
    val linkState: LinkState = LinkState.CONNECTING,
    val lastSync: String = nowHm(),
    val feed: List<FeedItem> = emptyList(),
    val filter: FeedFilter = FeedFilter.ALL,
    val expandedId: String? = null,
)

class MessagesViewModel(private val repository: OpcRepository) : ViewModel() {

    private val _state = MutableStateFlow(MessagesUiState())
    val state: StateFlow<MessagesUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.linkState.collect { link -> _state.value = _state.value.copy(linkState = link) }
        }
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true)
        viewModelScope.launch {
            val result = repository.feed()
            _state.value = _state.value.copy(
                loading = false,
                offline = result.offline,
                lastSync = nowHm(),
                feed = result.data,
            )
        }
    }

    fun selectFilter(filter: FeedFilter) {
        _state.value = _state.value.copy(filter = filter, expandedId = null)
    }

    /** 点一次展开详情，再点一次收起。 */
    fun toggleExpanded(id: String) {
        _state.value = _state.value.copy(expandedId = if (_state.value.expandedId == id) null else id)
    }
}
