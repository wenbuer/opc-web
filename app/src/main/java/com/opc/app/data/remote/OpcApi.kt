package com.opc.app.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

/**
 * opc-web 需要补的移动端接口（服务端未实现时全部返回 null，仓库层回落到演示数据）。
 * 鉴权头 X-OPC-Token 由 NetworkFactory 统一注入。
 */
interface OpcApi {

    @GET("/api/ping")
    suspend fun ping(): PingDto?

    @POST("/api/pair")
    suspend fun pair(@Body body: PairRequestDto): PairResponseDto?

    @GET("/api/projects")
    suspend fun projects(): List<ProjectDto>?

    @GET("/api/overview")
    suspend fun overview(): OverviewDto?

    @GET("/api/queue")
    suspend fun queue(): List<TaskDto>?

    @GET("/api/pending")
    suspend fun pending(): List<PendingDto>?

    @GET("/api/feed")
    suspend fun feed(): List<FeedDto>?

    @POST("/api/dispatch")
    suspend fun dispatch(@Body body: DispatchDto): AckDto?

    @POST("/api/piyue")
    suspend fun verdict(@Body body: VerdictDto): AckDto?

    @POST("/api/plan-pause")
    suspend fun pause(@Body body: PauseDto): AckDto?
}

@Serializable
data class PingDto(val version: String = "", val name: String = "opc-web")

@Serializable
data class PairRequestDto(
    val code: String,
    @SerialName("deviceName") val deviceName: String,
    @SerialName("deviceCode") val deviceCode: String,
    val platform: String,
)

@Serializable
data class PairResponseDto(
    val token: String = "",
    @SerialName("deviceCode") val deviceCode: String = "",
    @SerialName("serverVersion") val serverVersion: String = "",
    @SerialName("defaultProject") val defaultProject: String? = null,
    val projects: List<ProjectDto> = emptyList(),
)

@Serializable
data class ProjectDto(
    val id: String = "",
    val name: String = "",
    @SerialName("roleCount") val roleCount: Int = 0,
    @SerialName("runningSubtasks") val runningSubtasks: Int = 0,
)

@Serializable
data class OverviewDto(
    @SerialName("doneToday") val doneToday: Int = 0,
    val running: Int = 0,
    @SerialName("pendingReview") val pendingReview: Int = 0,
    @SerialName("costTodayYuan") val costTodayYuan: Double = 0.0,
    @SerialName("tokensToday") val tokensToday: Long = 0,
    @SerialName("weekCosts") val weekCosts: List<Double> = emptyList(),
    val roles: List<RoleDto> = emptyList(),
    val events: List<EventDto> = emptyList(),
)

@Serializable
data class RoleDto(
    val code: String = "",
    val name: String = "",
    val note: String = "",
    val state: String = "IDLE",
)

@Serializable
data class EventDto(
    val time: String = "",
    val text: String = "",
    val kind: String = "INFO",
)

@Serializable
data class TaskDto(
    @SerialName("taskNo") val taskNo: String = "",
    val text: String = "",
    val status: String = "QUEUED",
    val subtasks: List<SubTaskDto> = emptyList(),
    @SerialName("createdAt") val createdAt: String = "",
)

@Serializable
data class SubTaskDto(
    val no: String = "",
    val title: String = "",
    val role: String = "",
    val expect: String = "",
    val status: String = "DISPATCHED",
    val progress: Float = 0f,
    val rounds: Int = 0,
    @SerialName("scheduledAt") val scheduledAt: String? = null,
)

@Serializable
data class PendingDto(
    @SerialName("taskNo") val taskNo: String = "",
    @SerialName("subNo") val subNo: String = "",
    val title: String = "",
    val summary: String = "",
    val risk: String = "",
    val recommend: String = "",
    @SerialName("recommendWhy") val recommendWhy: String = "",
    val options: List<String> = emptyList(),
    @SerialName("proposedBy") val proposedBy: String = "",
    @SerialName("proposedAt") val proposedAt: String = "",
    @SerialName("waitedHours") val waitedHours: Int = 0,
)

@Serializable
data class FeedDto(
    val id: String = "",
    val type: String = "ALERT",
    val title: String = "",
    val body: String = "",
    val time: String = "",
    val chips: List<String> = emptyList(),
    val read: Boolean = true,
)

@Serializable
data class DispatchDto(val text: String)

@Serializable
data class VerdictDto(
    @SerialName("taskNo") val taskNo: String,
    @SerialName("subNo") val subNo: String,
    val verdict: String,
    val opinion: String = "",
)

@Serializable
data class PauseDto(val paused: Boolean)

@Serializable
data class AckDto(val ok: Boolean = true, val message: String? = null)
