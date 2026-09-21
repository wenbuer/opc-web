package com.opc.app.data

import com.opc.app.domain.TaskDiary
import com.opc.app.domain.FeedItem
import com.opc.app.domain.OverviewStats
import com.opc.app.domain.PendingItem
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.ServerConfig
import com.opc.app.domain.TaskSummary
import com.opc.app.domain.TunnelProfile
import com.opc.app.domain.Verdict
import com.opc.app.domain.WireConfig
import kotlinx.coroutines.flow.Flow

/**
 * 配对结果：服务端配置 + 隧道档案（老二维码没有隧道时为 null）+ 非致命告警
 * （例如设备 confirm 没走通，写接口会被服务端挡）。
 */
data class PairResult(
    val config: ServerConfig,
    val tunnel: TunnelProfile? = null,
    val warning: String? = null,
)

/**
 * UI 只依赖这个接口。服务端接口（/api/pair、/api/overview …）尚未在 opc-web 落地，
 * 所以实现走「在线优先 → 本地缓存 → 演示数据」三级回落，保证没服务端也能把整个 App 走通。
 */
interface OpcRepository {

    val config: Flow<ServerConfig?>
    val project: Flow<ProjectInfo?>
    val linkState: Flow<LinkState>

    suspend fun overview(): ResultData<OverviewStats>
    suspend fun tasks(): ResultData<List<TaskSummary>>
    suspend fun taskDiaries(): ResultData<List<TaskDiary>>
    suspend fun pending(): ResultData<List<PendingItem>>
    suspend fun feed(): ResultData<List<FeedItem>>

    suspend fun dispatch(text: String): Result<Unit>
    suspend fun verdict(taskNo: String, subNo: String, v: Verdict, opinion: String): Result<Unit>
    suspend fun pauseChain(paused: Boolean): Result<Unit>
    suspend fun switchProject(id: String): Result<Unit>

    /** 连接前预检：同一个方法给「服务端在线」那一行用。 */
    suspend fun ping(baseUrl: String): Result<String>

    /**
     * 配对：手机先自己生成密钥对，只把公钥放进请求；响应里的 tunnel{} 用来补全隧道档案。
     * wire 是二维码里的骨架（可为 null）。老二维码无隧道时照旧成功，只是隧道为 null。
     */
    suspend fun pair(
        baseUrl: String,
        code: String,
        deviceName: String,
        wire: WireConfig? = null,
    ): Result<PairResult>

    suspend fun unpair()
}