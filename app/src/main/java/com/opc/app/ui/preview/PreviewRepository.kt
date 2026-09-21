package com.opc.app.ui.preview

import com.opc.app.data.LinkState
import com.opc.app.data.OpcRepository
import com.opc.app.data.ResultData
import com.opc.app.domain.FeedItem
import com.opc.app.domain.OverviewStats
import com.opc.app.domain.PendingItem
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.ServerConfig
import com.opc.app.domain.TaskDiary
import com.opc.app.domain.TaskSummary
import com.opc.app.domain.Verdict
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf

/**
 * 预览专用的仓库桩：只吐演示数据，网络与落盘一律空实现。
 * 用途仅限 IDE 预览面板 —— 预览里点「下达 / 裁决 / 解除配对」不会产生任何副作用。
 */
internal class PreviewRepository : OpcRepository {

    private val demoConfig = ServerConfig(
        baseUrl = "192.168.1.20:8901",
        token = "preview",
        deviceCode = "DEV-7F3A-91C2",
        deviceName = "Pixel 9 · 主人手机",
        serverVersion = "1.18.0",
        pairedAt = 0L,
    )

    override val config: Flow<ServerConfig?> = flowOf(demoConfig)
    override val project: Flow<ProjectInfo?> = flowOf(ProjectInfo("opc-app", "OPC-APP", 4, 3))
    override val linkState: Flow<LinkState> = flowOf(LinkState.ONLINE)

    override suspend fun overview(): ResultData<OverviewStats> =
        ResultData(com.opc.app.data.DemoData.overview())

    override suspend fun tasks(): ResultData<List<TaskSummary>> =
        ResultData(com.opc.app.data.DemoData.tasks())

    override suspend fun taskDiaries(): ResultData<List<TaskDiary>> =
        ResultData(com.opc.app.data.DemoData.taskDiaries())

    override suspend fun pending(): ResultData<List<PendingItem>> =
        ResultData(com.opc.app.data.DemoData.pending())

    override suspend fun feed(): ResultData<List<FeedItem>> =
        ResultData(com.opc.app.data.DemoData.feed())

    override suspend fun dispatch(text: String): Result<Unit> = Result.success(Unit)
    override suspend fun verdict(taskNo: String, subNo: String, v: Verdict, opinion: String): Result<Unit> =
        Result.success(Unit)

    override suspend fun pauseChain(paused: Boolean): Result<Unit> = Result.success(Unit)
    override suspend fun switchProject(id: String): Result<Unit> = Result.success(Unit)
    override suspend fun ping(baseUrl: String): Result<String> = Result.success("1.18.0")
    override suspend fun pair(baseUrl: String, code: String, deviceName: String): Result<ServerConfig> =
        Result.success(demoConfig)

    override suspend fun unpair() = Unit
}
