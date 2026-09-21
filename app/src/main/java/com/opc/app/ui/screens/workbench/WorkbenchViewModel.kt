package com.opc.app.ui.screens.workbench

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.domain.TaskActivity
import com.opc.app.domain.TaskDiary
import com.opc.app.domain.TaskStatus
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
    val diaries: List<TaskDiary> = emptyList(),
    /** 「@」能点到的角色，格式 (码, 名字)。 */
    val roles: List<Pair<String, String>> = emptyList(),
    val draft: String = "",
    val mentionOpen: Boolean = false,
    val sending: Boolean = false,
    val error: String? = null,
)

class WorkbenchViewModel(private val repository: OpcRepository) : ViewModel() {

    private val _state = MutableStateFlow(WorkbenchUiState())
    val state: StateFlow<WorkbenchUiState> = _state.asStateFlow()

    /** 本机刚下达、服务端还没回执的任务，先挂在流水最前面。 */
    private val localDispatches = mutableListOf<TaskDiary>()

    init {
        viewModelScope.launch {
            repository.linkState.collect { link -> _state.value = _state.value.copy(linkState = link) }
        }
        refresh()
    }

    fun refresh() {
        _state.value = _state.value.copy(loading = true)
        viewModelScope.launch {
            val diaries = repository.taskDiaries()
            val roles = repository.overview().data.roles
                .filter { it.code.startsWith("R") && it.code != "R0" && it.code != "R1" }
                .map { it.code to it.name }
            _state.value = _state.value.copy(
                loading = false,
                offline = diaries.offline,
                lastSync = nowHm(),
                // 时间升序：任务按发生顺序排下去，所有任务都在这一屏
                diaries = (diaries.data + localDispatches).sortedBy { it.createdTime },
                roles = roles,
            )
        }
    }

    fun onDraftChange(value: String) {
        // 打字打到「@」就把角色选择行推到输入框上方
        _state.value = _state.value.copy(draft = value, mentionOpen = value.trimEnd().endsWith("@"))
    }

    fun openMention() {
        _state.value = _state.value.copy(mentionOpen = true)
    }

    fun dismissMention() {
        _state.value = _state.value.copy(mentionOpen = false)
    }

    /** 点角色：把末尾那个 @ 换成 @R4。 */
    fun pickMention(code: String) {
        val draft = _state.value.draft.trimEnd().removeSuffix("@")
        _state.value = _state.value.copy(draft = draft + "@" + code + " ", mentionOpen = false)
    }

    /** 三个快捷芯片只是把意图写进输入框，不直接发送——发什么话仍由人过一眼。 */
    fun applyQuickIntent(prefix: String) {
        _state.value = _state.value.copy(draft = prefix, mentionOpen = false)
    }

    /**
     * 弹层里点快捷意图：把前缀拼在已有草稿后面，不覆盖。
     * 覆盖会把用户已经打的半句话吃掉；只写前缀、不发送，是为了让人还能接着补完整。
     */
    fun appendQuickIntent(prefix: String) {
        val draft = _state.value.draft
        _state.value = _state.value.copy(
            draft = if (draft.isBlank()) prefix else draft.trimEnd() + " " + prefix,
            mentionOpen = false,
        )
    }

    fun send() {
        val text = _state.value.draft.trim()
        if (text.isEmpty()) return
        val time = nowHm()
        val no = "T-" + (900 + localDispatches.size + 1)
        localDispatches += TaskDiary(
            taskNo = no,
            text = text,
            createdTime = time,
            status = TaskStatus.QUEUED,
            activities = listOf(
                TaskActivity(
                    time = time,
                    subject = "R1",
                    subjectName = "老板助理",
                    action = com.opc.app.domain.ActivityAction.DECOMPOSED,
                    targetName = "收到，正在拆解…",
                ),
            ),
        )
        _state.value = _state.value.copy(
            diaries = (_state.value.diaries + localDispatches.last()).sortedBy { it.createdTime },
            draft = "",
            mentionOpen = false,
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
