package com.opc.app.data

import com.opc.app.domain.ChatItem
import com.opc.app.domain.EventKind
import com.opc.app.domain.FeedItem
import com.opc.app.domain.FeedType
import com.opc.app.domain.OpcEvent
import com.opc.app.domain.OverviewStats
import com.opc.app.domain.PendingItem
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.RoleState
import com.opc.app.domain.RoleStatus
import com.opc.app.domain.SubTask
import com.opc.app.domain.SubTaskStatus
import com.opc.app.domain.TaskStatus
import com.opc.app.domain.TaskSummary

/**
 * 演示数据：文案与 design/index.html 的截图一致，方便对照视觉稿验收。
 * 服务端一旦可用，这些数据会被真实数据整体替换，不进任何计算。
 */
object DemoData {

    val project = ProjectInfo(id = "opc-app", name = "OPC-APP", roleCount = 4, runningSubtasks = 3)

    fun overview(): OverviewStats = OverviewStats(
        doneToday = 3,
        running = 3,
        pendingReview = 1,
        costTodayYuan = 4.28,
        tokensToday = 1_940_000,
        weekCosts = listOf(1.4, 2.2, 1.7, 3.3, 2.5, 4.28, 1.1),
        roles = listOf(
            RoleStatus("R0", "创始人（你）", "1 项待裁决 · 2 项待批阅", RoleState.COMMANDING),
            RoleStatus("R1", "老板助理", "T-041 拆解中 · 群聊 2 条待看", RoleState.RUNNING),
            RoleStatus("R4", "产品设计师", "T-041-S1 产出中", RoleState.RUNNING),
            RoleStatus("R6", "前端工程师", "空闲 · 上次 08:20 收工", RoleState.IDLE),
        ),
        events = listOf(
            OpcEvent("09:41", "R1 派发 T-041-S1「信息架构与流程图」给 R4"),
            OpcEvent("09:28", "T-040 产出归档，回报 4.2k 字", EventKind.DONE),
            OpcEvent("09:12", "T-039-S2 触发工具护栏中止，已按阻塞收口", EventKind.ERROR),
            OpcEvent("08:55", "T-039 完成，等待批阅", EventKind.DONE),
        ),
    )

    fun tasks(): List<TaskSummary> = listOf(
        TaskSummary(
            taskNo = "T-041",
            text = "以产品设计师身份做一版 OPC 移动端界面，先出信息架构和关键流程图，明早给我看",
            status = TaskStatus.RUNNING,
            createdAt = "09:41",
            subtasks = listOf(
                SubTask(
                    no = "S1",
                    title = "信息架构与关键流程图",
                    role = "R4",
                    expect = "页面清单 + 导航结构 + 3 张主流程图（md）",
                    status = SubTaskStatus.DISPATCHED,
                    progress = 0.64f,
                    rounds = 12,
                ),
                SubTask(
                    no = "S2",
                    title = "视觉草案：3 个关键屏",
                    role = "R4",
                    expect = "PNG 稿 + 设计说明，先做扫码连接 / 工作台 / 批阅台",
                    status = SubTaskStatus.QUEUED,
                    scheduledAt = "18:00",
                ),
            ),
        ),
        TaskSummary(
            taskNo = "T-040",
            text = "移动端信息架构调研",
            status = TaskStatus.DONE,
            createdAt = "08:30",
            subtasks = emptyList(),
        ),
    )

    fun chat(): List<ChatItem> = listOf(
        ChatItem.DayDivider("d1", "今天"),
        ChatItem.SystemLine("s1", "你下达 T-041", "09:41"),
        ChatItem.Mine(
            id = "m1",
            text = "R4 以产品设计师身份做一版 OPC 移动端界面，先出信息架构和关键流程图，明早给我看。",
            time = "09:41",
        ),
        ChatItem.Agent(
            id = "a1",
            who = "R1 老板助理",
            avatar = "R1",
            text = "收到。已拆成 2 个子任务，按峰谷把重活排到 18:00 后开跑。",
            time = "09:41",
        ),
        ChatItem.Subtasks(
            id = "st1",
            taskNo = "T-041",
            items = tasks().first().subtasks,
        ),
        ChatItem.Progress(
            id = "p1",
            who = "产品设计师 R4",
            avatar = "R4",
            subNo = "T-041-S1",
            text = "正在整理导航结构，已定 5 个一级入口，正在补「扫码连接」的分支流程…",
            progress = 0.64f,
            rounds = 12,
        ),
    )

    fun pending(): List<PendingItem> = listOf(
        PendingItem(
            taskNo = "T-039",
            subNo = "S2",
            title = "首页改版是否增加第三档订阅价？",
            summary = "竞品均已上探第三档。新增档位需改 3 处定价逻辑与支付回落，评估工期 2.5 天；不改则本月转化预计持平。",
            risk = "中",
            recommend = "B 灰度新增",
            recommendWhy = "先上第三档但只挂 2 个入口灰度，两周看转化再全量，避免一次性改 3 处定价逻辑。",
            options = listOf("A 全量新增 · 工期 2.5 天 · 成本 ¥18", "B 灰度新增 · 工期 1 天 · 成本 ¥7"),
            proposedBy = "R4",
            proposedAt = "09:12",
            waitedHours = 4,
        ),
    )

    fun feed(): List<FeedItem> = listOf(
        FeedItem(
            id = "f1",
            type = FeedType.DAILY,
            title = "09-24 战报：3 完成 / 1 待裁决",
            body = "成本 ¥4.28，T-039-S2 卡在工具护栏，建议今天内裁决订阅档位。",
            time = "08:20",
            chips = listOf("每日简报"),
            read = false,
        ),
        FeedItem(
            id = "f2",
            type = FeedType.OUTPUT,
            title = "T-040-移动端信息架构调研.md",
            body = "R4 产出，4.2k 字，已归档。",
            time = "09:28",
            chips = listOf("4.2k 字", "md", "已归档"),
            read = false,
        ),
        FeedItem(
            id = "f3",
            type = FeedType.KNOWLEDGE,
            title = "知识库更新",
            body = "「移动端产品决策」主题新增 1 篇，与既有 2 篇合并。",
            time = "09:30",
            chips = listOf("知识库"),
            read = true,
        ),
        FeedItem(
            id = "f4",
            type = FeedType.ALERT,
            title = "系统告警 · 执行护栏",
            body = "T-039-S2 工具调用 320 次触顶，已中止并按阻塞收口，等待裁决后重跑。",
            time = "昨天 23:41",
            chips = listOf("护栏", "阻塞"),
            read = true,
        ),
        FeedItem(
            id = "f5",
            type = FeedType.SCHEDULE,
            title = "定时任务已跑",
            body = "「每周成本复盘」已生成 T-037 并派给 R2。",
            time = "昨天 18:00",
            chips = listOf("定时"),
            read = true,
        ),
    )
}
