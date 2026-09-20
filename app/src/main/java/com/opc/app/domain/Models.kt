package com.opc.app.domain

/** 服务端配对信息。token 只存本机 DataStore，不上云。 */
data class ServerConfig(
    val baseUrl: String,
    val token: String,
    val deviceCode: String,
    val deviceName: String,
    val serverVersion: String,
    val pairedAt: Long,
)

data class ProjectInfo(
    val id: String,
    val name: String,
    val roleCount: Int,
    val runningSubtasks: Int,
)

data class OverviewStats(
    val doneToday: Int,
    val running: Int,
    val pendingReview: Int,
    val costTodayYuan: Double,
    val tokensToday: Long,
    val weekCosts: List<Double>,
    val roles: List<RoleStatus>,
    val events: List<OpcEvent>,
)

data class RoleStatus(
    val code: String,
    val name: String,
    val note: String,
    val state: RoleState,
)

enum class RoleState { COMMANDING, RUNNING, IDLE, BLOCKED }

data class OpcEvent(
    val time: String,
    val text: String,
    val kind: EventKind = EventKind.INFO,
)

enum class EventKind { INFO, DONE, ERROR }

data class TaskSummary(
    val taskNo: String,
    val text: String,
    val status: TaskStatus,
    val subtasks: List<SubTask>,
    val createdAt: String,
)

enum class TaskStatus { QUEUED, DECOMPOSING, RUNNING, DONE, BLOCKED }

data class SubTask(
    val no: String,
    val title: String,
    val role: String,
    val expect: String,
    val status: SubTaskStatus,
    val progress: Float = 0f,
    val rounds: Int = 0,
    val scheduledAt: String? = null,
)

enum class SubTaskStatus { DISPATCHED, RUNNING, QUEUED, DONE, BLOCKED }

data class PendingItem(
    val taskNo: String,
    val subNo: String,
    val title: String,
    val summary: String,
    val risk: String,
    val recommend: String,
    val recommendWhy: String,
    val options: List<String>,
    val proposedBy: String,
    val proposedAt: String,
    val waitedHours: Int,
)

enum class Verdict { APPROVE, REJECT, AMEND }

data class FeedItem(
    val id: String,
    val type: FeedType,
    val title: String,
    val body: String,
    val time: String,
    val chips: List<String> = emptyList(),
    val read: Boolean = true,
)

enum class FeedType { DAILY, OUTPUT, KNOWLEDGE, ALERT, SCHEDULE }

/** 工作台聊天流的一条。 */
sealed interface ChatItem {
    val id: String

    data class DayDivider(override val id: String, val text: String) : ChatItem
    data class SystemLine(override val id: String, val text: String, val time: String) : ChatItem
    data class Mine(override val id: String, val text: String, val time: String) : ChatItem
    data class Agent(
        override val id: String,
        val who: String,
        val avatar: String,
        val text: String,
        val time: String,
    ) : ChatItem

    data class Subtasks(
        override val id: String,
        val taskNo: String,
        val items: List<SubTask>,
    ) : ChatItem

    data class Progress(
        override val id: String,
        val who: String,
        val avatar: String,
        val subNo: String,
        val text: String,
        val progress: Float,
        val rounds: Int,
    ) : ChatItem
}
