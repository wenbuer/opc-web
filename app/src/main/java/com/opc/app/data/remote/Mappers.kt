package com.opc.app.data.remote

import com.opc.app.domain.EventKind
import com.opc.app.domain.OpcEvent
import com.opc.app.domain.OverviewStats
import com.opc.app.domain.PendingItem
import com.opc.app.domain.RoleState
import com.opc.app.domain.RoleStatus
import com.opc.app.domain.SubTask
import com.opc.app.domain.SubTaskStatus
import com.opc.app.domain.TaskStatus
import com.opc.app.domain.TaskSummary

/**
 * 服务端 DTO → 领域模型。枚举用字符串容错解析：服务端将来加状态不会崩客户端。
 */
fun OverviewDto.toDomain(): OverviewStats = OverviewStats(
    doneToday = doneToday,
    running = running,
    pendingReview = pendingReview,
    costTodayYuan = costTodayYuan,
    tokensToday = tokensToday,
    weekCosts = weekCosts.ifEmpty { List(7) { 0.0 } },
    roles = roles.map { RoleStatus(it.code, it.name, it.note, it.state.toRoleState()) },
    events = events.map { OpcEvent(it.time, it.text, it.kind.toEventKind()) },
)

fun TaskDto.toDomain(): TaskSummary = TaskSummary(
    taskNo = taskNo,
    text = text,
    status = status.toTaskStatus(),
    createdAt = createdAt,
    subtasks = subtasks.map { it.toDomain() },
)

fun SubTaskDto.toDomain(): SubTask = SubTask(
    no = no,
    title = title,
    role = role,
    expect = expect,
    status = status.toSubTaskStatus(),
    progress = progress,
    rounds = rounds,
    scheduledAt = scheduledAt,
)

fun PendingDto.toDomain(): PendingItem = PendingItem(
    taskNo = taskNo,
    subNo = subNo,
    title = title,
    summary = summary,
    risk = risk,
    recommend = recommend,
    recommendWhy = recommendWhy,
    options = options,
    proposedBy = proposedBy,
    proposedAt = proposedAt,
    waitedHours = waitedHours,
)

private fun String.toRoleState(): RoleState = when (uppercase()) {
    "COMMANDING" -> RoleState.COMMANDING
    "RUNNING" -> RoleState.RUNNING
    "BLOCKED" -> RoleState.BLOCKED
    else -> RoleState.IDLE
}

private fun String.toEventKind(): EventKind = when (uppercase()) {
    "DONE" -> EventKind.DONE
    "ERROR" -> EventKind.ERROR
    else -> EventKind.INFO
}

private fun String.toTaskStatus(): TaskStatus = when (uppercase()) {
    "DECOMPOSING" -> TaskStatus.DECOMPOSING
    "RUNNING" -> TaskStatus.RUNNING
    "DONE" -> TaskStatus.DONE
    "BLOCKED" -> TaskStatus.BLOCKED
    else -> TaskStatus.QUEUED
}

private fun String.toSubTaskStatus(): SubTaskStatus = when (uppercase()) {
    "RUNNING" -> SubTaskStatus.RUNNING
    "QUEUED" -> SubTaskStatus.QUEUED
    "DONE" -> SubTaskStatus.DONE
    "BLOCKED" -> SubTaskStatus.BLOCKED
    else -> SubTaskStatus.DISPATCHED
}
