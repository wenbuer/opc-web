package com.opc.app.data

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
import com.opc.app.domain.ChatItem
import com.opc.app.domain.FeedItem
import com.opc.app.domain.FeedType
import com.opc.app.domain.OverviewStats
import com.opc.app.domain.PendingItem
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.QrProtocol
import com.opc.app.domain.ServerConfig
import com.opc.app.domain.SubTask
import com.opc.app.domain.TaskSummary
import com.opc.app.domain.Verdict
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
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

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

    override suspend fun chat(): ResultData<List<ChatItem>> {
        val remote = tasks()
        val items = mutableListOf<ChatItem>()
        items += ChatItem.DayDivider("day-today", "今天")
        if (remote.data.isNotEmpty()) {
            items += ChatItem.SystemLine(
                id = "sys-0",
                text = "现有 " + remote.data.size + " 个任务 · " + remote.data.sumOf { it.subtasks.size } + " 个子任务",
                time = remote.data.first().createdAt,
            )
        }
        remote.data.forEach { task ->
            items += ChatItem.Mine("mine-" + task.taskNo, task.text, task.createdAt)
            if (task.subtasks.isNotEmpty()) {
                items += ChatItem.Agent(
                    id = "agent-" + task.taskNo,
                    who = "R1 老板助理",
                    avatar = "R1",
                    text = "收到。已拆成 " + task.subtasks.size + " 个子任务，按峰谷把重活排到谷时开跑。",
                    time = task.createdAt,
                )
                items += ChatItem.Subtasks("subs-" + task.taskNo, task.taskNo, task.subtasks)
            }
        }
        return if (items.size <= 1) ResultData(DemoData.chat(), offline = remote.offline) else ResultData(items, offline = remote.offline)
    }

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

    override suspend fun pair(baseUrl: String, code: String, deviceName: String): Result<ServerConfig> = runCatching {
        withContext(Dispatchers.IO) {
            val deviceCode = QrProtocol.newDeviceCode()
            val resp = apiFor(baseUrl).pair(
                PairRequestDto(code = code, deviceName = deviceName, deviceCode = deviceCode, platform = "android"),
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
            resp.projects.firstOrNull()?.let {
                store.saveProject(ProjectInfo(it.id, it.name, it.roleCount, it.runningSubtasks))
            }
            cfg
        }
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
