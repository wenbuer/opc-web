package com.opc.app.data

import com.opc.app.domain.ActivityAction
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
import com.opc.app.domain.TaskActivity
import com.opc.app.domain.TaskDiary
import com.opc.app.domain.TaskStatus
import com.opc.app.domain.TaskSummary

/**
 * 演示数据：文案与 design/index.html 的截图一致，方便对照视觉稿验收。
 * 服务端一旦可用，这些数据会被真实数据整体替换，不进任何计算。
 */
object DemoData {

    val project = ProjectInfo(id = "opc-app", name = "OPC-APP", roleCount = 4, runningSubtasks = 3)

    /** 角色码 → 中文名，工作台流水与「@ 指派」都用它。 */
    val roleNames: Map<String, String> = mapOf(
        "R1" to "老板助理",
        "R2" to "产品经理",
        "R4" to "产品设计师",
        "R6" to "前端工程师",
    )

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
        TaskSummary("T-040", "移动端信息架构调研", TaskStatus.DONE, emptyList(), "08:30"),
        TaskSummary("T-039", "首页改版定价方案评审", TaskStatus.DONE, emptyList(), "07:50"),
        TaskSummary("T-038", "昨日成本复盘", TaskStatus.DONE, emptyList(), "07:20"),
    )

    /** 工作台只放流水：谁在什么时候拆了、接了、交了、汇报了。执行细节不在这里。 */
    fun taskDiaries(): List<TaskDiary> = listOf(
        TaskDiary(
            taskNo = "T-038",
            text = "把昨天的 token 用量和成本拉一份复盘",
            createdTime = "07:20",
            status = TaskStatus.DONE,
            activities = listOf(
                act("07:20", "R1", ActivityAction.DECOMPOSED, null, "拆成 1 个子任务 · 指派 1 个角色"),
                act("07:22", "R2", ActivityAction.ACCEPTED, "S1", "成本复盘"),
                act("07:48", "R2", ActivityAction.COMPLETED, "S1", "成本复盘"),
                act("07:50", "R1", ActivityAction.REPORTED, "T-038", "已汇总回报 · 无需裁决"),
            ),
        ),
        TaskDiary(
            taskNo = "T-039",
            text = "首页改版要不要加第三档订阅价，出个建议",
            createdTime = "07:50",
            status = TaskStatus.DONE,
            activities = listOf(
                act("07:50", "R1", ActivityAction.DECOMPOSED, null, "拆成 2 个子任务 · 指派 2 个角色"),
                act("07:52", "R2", ActivityAction.ACCEPTED, "S1", "竞品档位与转化分析"),
                act("08:20", "R2", ActivityAction.COMPLETED, "S1", "竞品档位与转化分析"),
                act("08:22", "R4", ActivityAction.ACCEPTED, "S2", "改价影响面评估"),
                act("09:12", "R4", ActivityAction.COMPLETED, "S2", "改价影响面评估"),
                act("09:14", "R1", ActivityAction.REPORTED, "T-039", "1 项待你裁决"),
            ),
        ),
        TaskDiary(
            taskNo = "T-040",
            text = "调研一下同类工具在手机上都怎么做信息架构",
            createdTime = "08:30",
            status = TaskStatus.DONE,
            activities = listOf(
                act("08:30", "R1", ActivityAction.DECOMPOSED, null, "拆成 1 个子任务 · 指派 1 个角色"),
                act("08:32", "R4", ActivityAction.ACCEPTED, "S1", "移动端信息架构调研"),
                act("09:26", "R4", ActivityAction.COMPLETED, "S1", "移动端信息架构调研"),
                act("09:28", "R1", ActivityAction.REPORTED, "T-040", "已归档 4.2k 字 · 无需裁决"),
            ),
        ),
        TaskDiary(
            taskNo = "T-041",
            text = "以产品设计师身份做一版 OPC 移动端界面，先出信息架构和关键流程图，明早给我看",
            createdTime = "09:41",
            status = TaskStatus.RUNNING,
            activities = listOf(
                act("09:41", "R1", ActivityAction.DECOMPOSED, null, "拆成 2 个子任务 · 指派 1 个角色"),
                act("09:41", "R4", ActivityAction.ACCEPTED, "S1", "信息架构与关键流程图"),
            ),
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

    private fun act(
        time: String,
        subject: String,
        action: ActivityAction,
        target: String?,
        targetName: String?,
    ) = TaskActivity(
        time = time,
        subject = subject,
        subjectName = roleNames[subject] ?: subject,
        action = action,
        target = target,
        targetName = targetName,
    )
}
