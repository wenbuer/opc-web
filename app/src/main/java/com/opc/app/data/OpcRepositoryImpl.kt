package com.opc.app.data

import com.opc.app.data.remote.ConfirmDto
import com.opc.app.data.remote.NetworkFactory
import com.opc.app.data.remote.OpcApi
import com.opc.app.data.remote.OverviewDto
import com.opc.app.data.remote.PairRequestDto
import com.opc.app.data.remote.PauseDto
import com.opc.app.data.remote.DispatchDto
import com.opc.app.data.remote.FeedDto
import com.opc.app.data.remote.PendingDto
import com.opc.app.data.remote.SubTaskDto
import com.opc.app.data.remote.TaskDto
import com.opc.app.data.remote.VerdictDto
import com.opc.app.data.remote.toDomain
import com.opc.app.domain.ActivityAction
import com.opc.app.domain.FeedItem
import com.opc.app.domain.FeedType
import com.opc.app.domain.OverviewStats
import com.opc.app.domain.PendingItem
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.QrProtocol
import com.opc.app.domain.ServerConfig
import com.opc.app.domain.SubTask
import com.opc.app.domain.SubTaskStatus
import com.opc.app.domain.TaskActivity
import com.opc.app.domain.TaskDiary
import com.opc.app.domain.TaskStatus
import com.opc.app.domain.TaskSummary
import com.opc.app.domain.TunnelOffer
import com.opc.app.domain.Verdict
import com.opc.app.domain.WireConfig
import com.opc.app.tunnel.TunnelKeys
import com.opc.app.tunnel.WireGuardConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import retrofit2.HttpException
import java.io.IOException

/**
 * 在线优先、离线回落。三级顺序：服务端 → 本机缓存 → 演示数据。
 * 任何网络异常都在这里收口成 ResultData.offline，不往 UI 抛。
 */
class OpcRepositoryImpl(
    private val store: SettingsStore,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) : OpcRepository {

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        explicitNulls = false
    }

    override val config: Flow<ServerConfig?> = store.config
    override val project: Flow<ProjectInfo?> = store.project
    override val deviceConfirmed: Flow<Boolean> = store.deviceConfirmed

    init {
        // 鉴权头随配对信息走：换服务端/解配对后立刻生效
        scope.launch { store.config.collect { NetworkFactory.token = it?.token } }
    }

    override val linkState: Flow<LinkState> =
        combine(store.config, store.demoMode, pollTick()) { cfg, demo, reachable ->
            when {
                cfg == null -> LinkState.UNPAIRED
                demo || cfg.baseUrl == SettingsStore.DEMO_BASE_URL -> LinkState.OFFLINE
                reachable == null -> LinkState.CONNECTING
                reachable -> LinkState.ONLINE
                else -> LinkState.OFFLINE
            }
        }.distinctUntilChanged()

    /** 配对后每 20 秒探一次服务端；未配对不探，省电。 */
    private fun pollTick(): Flow<Boolean?> = flow {
        while (true) {
            val cfg = store.currentConfig()
            emit(
                when {
                    cfg == null || cfg.baseUrl == SettingsStore.DEMO_BASE_URL -> null
                    else -> runCatching { api(cfg).ping() }.getOrNull() != null
                },
            )
            delay(if (cfg == null) 10_000 else 20_000)
        }
    }

    // ---------- 读 ----------

    override suspend fun overview(): ResultData<OverviewStats> {
        val cfg = store.currentConfig()
        if (cfg != null && cfg.baseUrl != SettingsStore.DEMO_BASE_URL) {
            val dto = call { api(cfg).overview() }
            if (dto != null) {
                store.saveCache(KEY_OVERVIEW, json.encodeToString(OverviewDto.serializer(), dto))
                return ResultData(dto.toDomain())
            }
            readCache(KEY_OVERVIEW, OverviewDto.serializer())?.let {
                return ResultData(it.toDomain(), offline = true, cachedAt = System.currentTimeMillis(), error = "服务端不可达")
            }
        }
        return ResultData(DemoData.overview(), offline = true, error = if (cfg == null) null else "服务端不可达")
    }

    override suspend fun tasks(): ResultData<List<TaskSummary>> {
        val cfg = store.currentConfig()
        if (cfg != null && cfg.baseUrl != SettingsStore.DEMO_BASE_URL) {
            val dto = call { api(cfg).queue() }
            if (!dto.isNullOrEmpty()) {
                store.saveCache(KEY_TASKS, json.encodeToString(ListSerializer(TaskDto.serializer()), dto))
                return ResultData(dto.map { it.toDomain() })
            }
            readCache(KEY_TASKS, ListSerializer(TaskDto.serializer()))?.let {
                return ResultData(it.map { t -> t.toDomain() }, offline = true, cachedAt = System.currentTimeMillis())
            }
        }
        return ResultData(DemoData.tasks(), offline = true)
    }

    override suspend fun taskDiaries(): ResultData<List<TaskDiary>> {
        val remote = tasks()
        if (remote.offline || remote.data.isEmpty()) {
            return ResultData(DemoData.taskDiaries(), offline = true)
        }
        return ResultData(remote.data.map { it.toDiary(roleNames = roleNameMap()) }, offline = false)
    }

    /** 角色码 → 中文名，用来把流水写成「产品设计师 R4 接收任务」这种人话。 */
    private suspend fun roleNameMap(): Map<String, String> =
        overview().data.roles.associate { it.code to it.name }

    override suspend fun pending(): ResultData<List<PendingItem>> {
        val cfg = store.currentConfig()
        if (cfg != null && cfg.baseUrl != SettingsStore.DEMO_BASE_URL) {
            val dto = call { api(cfg).pending() }
            if (dto != null) {
                store.saveCache(KEY_PENDING, json.encodeToString(ListSerializer(PendingDto.serializer()), dto))
                return ResultData(dto.map { it.toDomain() })
            }
            readCache(KEY_PENDING, ListSerializer(PendingDto.serializer()))?.let {
                return ResultData(it.map { p -> p.toDomain() }, offline = true, cachedAt = System.currentTimeMillis())
            }
        }
        return ResultData(DemoData.pending(), offline = true)
    }

    override suspend fun feed(): ResultData<List<FeedItem>> {
        val cfg = store.currentConfig()
        if (cfg != null && cfg.baseUrl != SettingsStore.DEMO_BASE_URL) {
            val dto = call { api(cfg).feed() }
            if (dto != null) {
                store.saveCache(KEY_FEED, json.encodeToString(ListSerializer(FeedDto.serializer()), dto))
                return ResultData(dto.map { it.toFeedItem() })
            }
            readCache(KEY_FEED, ListSerializer(FeedDto.serializer()))?.let {
                return ResultData(it.map { f -> f.toFeedItem() }, offline = true, cachedAt = System.currentTimeMillis())
            }
        }
        return ResultData(DemoData.feed(), offline = true)
    }

    // ---------- 写 ----------

    override suspend fun dispatch(text: String): Result<Unit> {
        val cfg = store.currentConfig()
        if (cfg == null) return Result.success(Unit)
        if (cfg.baseUrl == SettingsStore.DEMO_BASE_URL) return Result.success(Unit)
        return runCatching {
            withContext(Dispatchers.IO) {
                api(cfg).dispatch(DispatchDto(text)) ?: error("服务端未响应")
            }
            Unit
        }
    }

    override suspend fun verdict(taskNo: String, subNo: String, v: Verdict, opinion: String): Result<Unit> {
        val cfg = store.currentConfig()
        if (cfg == null || cfg.baseUrl == SettingsStore.DEMO_BASE_URL) return Result.success(Unit)
        return runCatching {
            withContext(Dispatchers.IO) {
                api(cfg).verdict(VerdictDto(taskNo, subNo, v.name, opinion)) ?: error("服务端未响应")
            }
            Unit
        }
    }

    override suspend fun pauseChain(paused: Boolean): Result<Unit> {
        val cfg = store.currentConfig()
        if (cfg == null || cfg.baseUrl == SettingsStore.DEMO_BASE_URL) return Result.success(Unit)
        return runCatching {
            withContext(Dispatchers.IO) {
                api(cfg).pause(PauseDto(paused)) ?: error("服务端未响应")
            }
            Unit
        }
    }

    override suspend fun switchProject(id: String): Result<Unit> = runCatching {
        val current = store.project.first() ?: DemoData.project
        store.saveProject(current.copy(id = id, name = if (id == DemoData.project.id) DemoData.project.name else id))
    }

    // ---------- 连接 ----------

    override suspend fun ping(baseUrl: String): Result<String> = runCatching {
        withContext(Dispatchers.IO) {
            val dto = apiFor(baseUrl).ping() ?: error("服务端未响应")
            dto.version.ifBlank { "opc-web" }
        }
    }

    override suspend fun pair(
        baseUrl: String,
        code: String,
        deviceName: String,
        wire: WireConfig?,
    ): Result<PairResult> = runCatching {
        withContext(Dispatchers.IO) {
            val deviceCode = QrProtocol.newDeviceCode()
            // 密钥对只在手机生成：私钥不出设备，出去换隧道参数的只有公钥
            val (privateKey, publicKey) = TunnelKeys.generate()
            val resp = apiFor(baseUrl).pair(
                PairRequestDto(
                    code = code,
                    deviceName = deviceName,
                    deviceCode = deviceCode,
                    platform = "android",
                    publicKey = publicKey,
                ),
            ) ?: error("配对码无效或已过期")
            val cfg = ServerConfig(
                baseUrl = baseUrl.trimEnd('/'),
                token = resp.token,
                deviceCode = resp.deviceCode.ifBlank { deviceCode },
                deviceName = deviceName,
                serverVersion = resp.serverVersion.ifBlank { "opc-web" },
                pairedAt = System.currentTimeMillis(),
            )
            store.savePairing(cfg)
            NetworkFactory.token = cfg.token
            resp.projects.firstOrNull()?.let {
                store.saveProject(ProjectInfo(it.id, it.name, it.roleCount, it.runningSubtasks))
            }
            val profile = WireGuardConfig.buildTunnelProfile(
                wire = wire,
                offer = resp.tunnel?.toDomain(),
                privateKey = privateKey,
                publicKey = publicKey,
                fallbackServerHost = hostOf(cfg.baseUrl),
            )
            if (profile != null) store.saveTunnelProfile(profile)
            if (profile == null) {
                PairResult(cfg, null, null)
            } else {
                val warning = confirmDevice(cfg)
                store.saveDeviceConfirmed(warning == null)
                PairResult(cfg, profile, warning, deviceConfirmed = warning == null)
            }
        }
    }.recoverCatching { error -> throw pairError(error) }

    /** 配对流程内部用的版本：返回给用户看的告警文案（null = 没问题）。 */
    private suspend fun confirmDevice(cfg: ServerConfig): String? = runCatching {
        withContext(Dispatchers.IO) {
            api(cfg).confirmDevice(ConfirmDto(cfg.deviceCode)) ?: error("服务端未响应")
        }
    }.exceptionOrNull()?.let { error ->
        "设备确认没走完（" + PairFailure.hint((error as? HttpException)?.code()) + "），写操作可能被拒"
    }

    /** 「我的」页的重试入口：配置还在就再确认一次，结果写回本机，界面据此收起重试入口。 */
    override suspend fun confirmDevice(): Result<Unit> = runCatching {
        val cfg = store.currentConfig() ?: error("还没配对")
        withContext(Dispatchers.IO) {
            api(cfg).confirmDevice(ConfirmDto(cfg.deviceCode)) ?: error("服务端未响应")
        }
        store.saveDeviceConfirmed(true)
        Unit
    }.onFailure { store.saveDeviceConfirmed(false) }

    private fun hostOf(baseUrl: String): String =
        baseUrl.substringAfter("://").substringBefore('/').substringBefore(':')

    /** 失败语义按契约 §5 分：HTTP 码优先，网络不通归「服务端不可达」，其余保留原文案。 */
    private fun pairError(error: Throwable): Throwable = when (error) {
        is HttpException -> IllegalStateException(PairFailure.hint(error.code()), error)
        is IOException -> IllegalStateException(PairFailure.hint(null), error)
        else -> error
    }

    override suspend fun unpair() {
        store.clearPairing()
    }

    // ---------- 内部 ----------

    private fun api(cfg: ServerConfig): OpcApi = NetworkFactory.api(cfg.baseUrl)

    private fun apiFor(baseUrl: String): OpcApi = NetworkFactory.api(baseUrl)

    /** 网络调用统一容错：远端没有这个接口时 Retrofit 抛 HttpException，这里吞掉当「没有」。 */
    private suspend fun <T> call(block: suspend () -> T?): T? =
        runCatching { withContext(Dispatchers.IO) { block() } }.getOrNull()

    private suspend fun <T> readCache(key: String, serializer: kotlinx.serialization.KSerializer<T>): T? {
        val raw = store.readCache(key) ?: return null
        return runCatching { json.decodeFromString(serializer, raw) }.getOrNull()
    }

    private companion object {
        const val KEY_OVERVIEW = "overview"
        const val KEY_TASKS = "tasks"
        const val KEY_PENDING = "pending"
        const val KEY_FEED = "feed"
    }
}

private fun com.opc.app.data.remote.TunnelDto.toDomain(): TunnelOffer = TunnelOffer(
    ip = ip.takeIf { it.isNotBlank() },
    cidr = cidr,
    serverPublicKey = serverPublicKey.takeIf { it.isNotBlank() },
    endpoint = endpoint.takeIf { it.isNotBlank() },
    allowedIps = allowedIps.takeIf { it.isNotBlank() },
    dns = dns?.takeIf { it.isNotBlank() },
    mtu = mtu.takeIf { it > 0 },
)

private fun FeedDto.toFeedItem(): FeedItem = FeedItem(
    id = id,
    type = when (type.uppercase()) {
        "DAILY" -> FeedType.DAILY
        "OUTPUT" -> FeedType.OUTPUT
        "KNOWLEDGE" -> FeedType.KNOWLEDGE
        "SCHEDULE" -> FeedType.SCHEDULE
        else -> FeedType.ALERT
    },
    title = title,
    body = body,
    time = time,
    chips = chips,
    read = read,
)

/** TaskSummary → 工作台流水：按时间排出「拆分 / 接收 / 完成 / 汇报」四类动作。 */
private fun TaskSummary.toDiary(roleNames: Map<String, String>): TaskDiary {
    val acts = mutableListOf<TaskActivity>()
    val assigneeCount = subtasks.map { it.role }.distinct().size
    acts += TaskActivity(
        time = createdAt,
        subject = "R1",
        subjectName = roleNames["R1"] ?: "老板助理",
        action = ActivityAction.DECOMPOSED,
        target = subtasks.firstOrNull()?.role,
        targetName = "拆成 " + subtasks.size + " 个子任务 · 指派 " + assigneeCount + " 个角色",
    )
    subtasks.forEach { sub ->
        acts += TaskActivity(
            time = sub.scheduledAt ?: createdAt,
            subject = sub.role,
            subjectName = roleNames[sub.role] ?: sub.role,
            action = ActivityAction.ACCEPTED,
            target = sub.no,
            targetName = sub.title,
        )
        if (sub.status == SubTaskStatus.DONE) {
            acts += TaskActivity(
                time = sub.scheduledAt ?: createdAt,
                subject = sub.role,
                subjectName = roleNames[sub.role] ?: sub.role,
                action = ActivityAction.COMPLETED,
                target = sub.no,
                targetName = sub.title,
            )
        }
    }
    if (status == TaskStatus.DONE) {
        acts += TaskActivity(
            time = createdAt,
            subject = "R1",
            subjectName = roleNames["R1"] ?: "老板助理",
            action = ActivityAction.REPORTED,
            target = taskNo,
            targetName = "已汇总回报，等批阅",
        )
    }
    return TaskDiary(taskNo, text, createdAt, status, acts)
}
