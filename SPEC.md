# opc-app 初版实现规格（v0.1）

安卓端 OPC 客户端。视觉稿：`design/index.html`（8 屏）。本文件是实现契约，subagent 之间靠它对齐。

## 0. 硬约束

- 包名 `com.opc.app`，Kotlin + Jetpack Compose + Material 3，minSdk 26 / compileSdk 35 / targetSdk 35。
- **不改 opc-web**（另一个仓库）。服务端接口未就绪时走离线演示数据。
- 界面**禁用 emoji，禁用扩展图标库**：只用 `androidx.compose.material.icons.Icons.Default/Filled/Outlined` 里的 **基础图标集**（material-icons-core，已被 material3 传递依赖）：
  `Menu, Search, Settings, Home, Person, Check, Close, Add, ArrowBack, ArrowForward, Refresh, Send, Notifications, MoreVert, Edit, Delete, Info, Warning, Lock, Star, Favorite, Email, Phone, Place, DateRange, AccountCircle, CheckCircle, List, Share, ThumbUp, Build, ExitToApp, KeyboardArrowDown, KeyboardArrowRight, KeyboardArrowUp, PlayArrow, Clear, Done, Call`
  需要更细的图标时**不引依赖**，用 `Icon(painter = ...)` 不成立，改用文字/形状表达，或从上面列表里挑最接近的。
- 所有字符串写死中文，直接内联在 Compose 里（初版不做 i18n）。

## 1. 目录与包结构

```
app/src/main/java/com/opc/app/
  OpcApplication.kt          appContainer
  AppContainer.kt             依赖装配（settingsStore / api / repository / mock）
  MainActivity.kt             setContent { OpcApp() } + enableEdgeToEdge
  domain/
    Models.kt                 领域模型（见 §3）
    QrProtocol.kt             opc://pair?... 解析 + 二维码位图生成
  data/
    SettingsStore.kt          DataStore：ServerConfig / ProjectInfo 持久化
    remote/OpcApi.kt          Retrofit 接口 + DTO（见 §4）
    remote/Network.kt         Retrofit/OkHttp/Json 构造、鉴权头、超时可调
    OpcRepository.kt          接口 + 实现：在线优先、失败回落 MockRepository
    DemoData.kt               离线演示数据（与设计稿文案一致）
  ui/
    theme/Color.kt Theme.kt Type.kt Shape.kt   （A 负责）
    components/                       （A 负责）
      StatusBar.kt  CapsuleChip.kt  TierTag.kt  MetricCard.kt  HeroCard.kt
      EventRow.kt   Bubble.kt  SubTaskCard.kt  SectionHeader.kt  SparkBars.kt
    nav/OpcApp.kt  Destinations.kt    （B 负责）
    screens/                          （B 负责）
      connect/ConnectScreen.kt ConnectViewModel.kt
      overview/OverviewScreen.kt OverviewViewModel.kt
      workbench/WorkbenchScreen.kt WorkbenchViewModel.kt
      review/ReviewScreen.kt ReviewViewModel.kt
      messages/MessagesScreen.kt MessagesViewModel.kt
      profile/ProfileScreen.kt ProfileViewModel.kt
    ViewModelFactory.kt               统一 VM 工厂（B 负责）
app/src/main/res/  values/themes.xml strings.xml  xml/  mipmap 等 （A 负责）
app/src/main/AndroidManifest.xml     （A 负责）
```

## 2. 视觉 token（A 定义，B 只用）

深色为主、浅色可用。种子色 = opc-web 的金 `#E8B73D`。语义：
```kotlin
// ui/theme/Color.kt —— 必须导出这些名字
val OpcGold = Color(0xFFE8B73D)
val OpcGoldContainer = Color(0xFF3A2F12)
val OpcIndigo = Color(0xFF4C6EF5)
val OpcIndigoContainer = Color(0xFF1E2748)
val OpcRed = Color(0xFFE74C3C)
val OpcRedContainer = Color(0xFF3A1A17)
val OpcGreen = Color(0xFF35B97C)
val OpcGreenContainer = Color(0xFF12301F)
val OpcDarkBackground = Color(0xFF0E1117)
val OpcDarkSurface = Color(0xFF161A21)
val OpcDarkSurfaceLow = Color(0xFF1B1F27)
val OpcDarkSurfaceHigh = Color(0xFF252932)
val OpcDarkSurfaceHighest = Color(0xFF2B2F39)
val OpcDarkText = Color(0xFFE8E4DC)
val OpcDarkDim = Color(0xFFA8A49C)
```
```kotlin
// ui/theme/Shape.kt —— 导出
val OpcShapes: Shapes          // extraSmall 8 / small 12 / medium 18 / large 24 / extraLarge 28
val CardRadius = 18.dp
val FabShape: Shape            // RoundedCornerShape(20.dp)，FAB 用圆角方块不用圆形
```
```kotlin
// ui/theme/Theme.kt —— 导出
@Composable fun OpcTheme(darkTheme: Boolean = true, content: @Composable () -> Unit)
object OpcSpacing { val xs=4.dp; val s=8.dp; val m=12.dp; val l=16.dp; val xl=22.dp; val xxl=28.dp }
val OpcScreenPadding; // 16.dp，页面左右统一
```
Typography：标题 21sp/600，正文 13sp/400，元信息 11sp，标签/编号用 `FontFamily.Monospace`。

## 3. 领域模型（A 不需要改，B 直接用）

```kotlin
package com.opc.app.domain

data class ServerConfig(
    val baseUrl: String,          // 形如 http://192.168.1.20:8901
    val token: String,
    val deviceCode: String,       // DEV-XXXX-XXXX
    val deviceName: String,
    val serverVersion: String,
    val pairedAt: Long,
)
data class ProjectInfo(val id: String, val name: String, val roleCount: Int, val runningSubtasks: Int)

data class OverviewStats(
    val doneToday: Int, val running: Int, val pendingReview: Int,
    val costTodayYuan: Double, val tokensToday: Long,
    val weekBarsYuan: List<Double>,      // 7 个点，最后一个=今天
    val roles: List<RoleStatus>,
    val events: List<OpcEvent>,
)
data class RoleStatus(val code: String, val name: String, val note: String, val state: RoleState)
enum class RoleState { COMMANDING, RUNNING, IDLE, BLOCKED }

data class OpcEvent(val time: String, val text: String, val kind: EventKind)
enum class EventKind { INFO, DONE, ERROR }

data class TaskSummary(
    val taskNo: String, val text: String, val status: TaskStatus,
    val subtasks: List<SubTask>, val createdAt: String,
)
enum class TaskStatus { QUEUED, DECOMPOSING, RUNNING, DONE, BLOCKED }
data class SubTask(
    val no: String,           // "S1"
    val title: String,
    val role: String,         // "R4"
    val expect: String,
    val status: SubTaskStatus,
    val progress: Float,      // 0f..1f
    val rounds: Int,
    val scheduledAt: String?, // 谷时排队时间
)
enum class SubTaskStatus { DISPATCHED, RUNNING, QUEUED, DONE, BLOCKED }

data class PendingItem(
    val taskNo: String, val subNo: String, val title: String,
    val summary: String, val risk: String,
    val recommend: String, val recommendWhy: String,
    val options: List<String>, val proposedBy: String, val proposedAt: String,
    val waitedHours: Int,
)
enum class Verdict { APPROVE, REJECT, AMEND }

data class FeedItem(
    val id: String, val type: FeedType, val title: String,
    val body: String, val time: String, val chips: List<String>, val read: Boolean,
)
enum class FeedType { DAILY, OUTPUT, KNOWLEDGE, ALERT, SCHEDULE }

// 工作台聊天流
sealed interface ChatItem {
    val id: String
    data class DayDivider(override val id: String, val text: String) : ChatItem
    data class SystemLine(override val id: String, val text: String, val time: String) : ChatItem
    data class Mine(override val id: String, val text: String, val time: String) : ChatItem
    data class Agent(override val id: String, val who: String, val avatar: String, val text: String, val time: String) : ChatItem
    data class Subtasks(override val id: String, val taskNo: String, val items: List<SubTask>) : ChatItem
    data class Progress(override val id: String, val who: String, val avatar: String, val subNo: String, val text: String, val progress: Float, val rounds: Int) : ChatItem
}
```

## 4. 仓库接口（B 只依赖它）

```kotlin
package com.opc.app.data

interface OpcRepository {
    val config: Flow<ServerConfig?>
    val project: Flow<ProjectInfo?>
    /** 在线优先，服务端不可达时返回演示数据并把 offline 置 true */
    suspend fun overview(): ResultData<OverviewStats>
    suspend fun tasks(): ResultData<List<TaskSummary>>
    suspend fun chat(): ResultData<List<ChatItem>>
    suspend fun pending(): ResultData<List<PendingItem>>
    suspend fun feed(): ResultData<List<FeedItem>>
    suspend fun dispatch(text: String): Result<Unit>
    suspend fun verdict(taskNo: String, subNo: String, v: Verdict, opinion: String): Result<Unit>
    suspend fun pauseChain(paused: Boolean): Result<Unit>
    suspend fun switchProject(id: String): Result<Unit>
    suspend fun unpair(): Unit
    /** 配对：扫码/手填 → 校验 → 落盘 */
    suspend fun pair(baseUrl: String, code: String, deviceName: String): Result<ServerConfig>
    suspend fun ping(baseUrl: String): Result<String>   // 返回服务端版本
}
data class ResultData<T>(val data: T, val offline: Boolean, val error: String? = null)
```
`OpcRepository` 由 `AppContainer` 提供单例：`container.repository`、`container.settingsStore`。

## 5. 页面行为（B 实现，对齐 design/index.html）

| 屏 | 要点 |
|---|---|
| ConnectScreen | 未配对时是首屏。上半：相机取景区（ZXing `DecoratedBarcodeView` 用 AndroidView 包），四角描边 + 扫描线动画。下半：配对码 6 位输入（本地校验格式）、地址输入、三项预检（同网段/服务端在线/设备白名单）状态行、「配对并连接」。成功后跳 Overview，并弹出配对成功卡（设备码/版本/项目选择）。 |
| OverviewScreen | 顶栏「作战面板」+ 项目芯片 + 连接态；Hero 卡（今日结论 + 7 日柱图）；三指标；组织列表（R0/R1/RX 等级色）；实时事件流。下拉刷新。 |
| WorkbenchScreen | 聊天室：ChatItem 列表渲染（气泡/系统行/子任务卡/进度卡）；底部输入区 + 三个快捷芯片（立即执行/指派角色/定时）；顶部 AppBar 显示群成员头像（首字母圆）+ 在线态。发送 = `dispatch`。 |
| ReviewScreen | 指标 + 等待告警条 + 待裁决卡（标题/摘要/R1 建议/选项芯片）+ 底部吸底三键（批准/驳回/修改）→ `verdict`。下方「工作内容」列表。 |
| MessagesScreen | 分类芯片 + 按日期分组卡片流；点击展开详情。 |
| ProfileScreen | 服务端连接信息、通知开关（本地开关即可）、远程运行开关（`pauseChain`）、解除配对（`unpair`）。 |

底部导航 5 项：总览 / 工作台 / 批阅台 / 消息 / 我的，激活态胶囊背景 + 顶栏徽标计数。未配对时只显示 ConnectScreen。

## 6. 联网契约（照设计稿「服务端要补的」写，服务端未实现——失败即回落演示数据）

- `GET /api/ping` → `{"version":"1.18.0"}`
- `POST /api/pair` body `{"code","deviceName","deviceCode","platform"}` → `{"token","deviceCode","serverVersion","projects":[{"id","name"}]}`
- `GET /api/projects` → `[{"id","name"}]`
- `GET /api/overview` → OverviewStats 同构 JSON
- `POST /api/dispatch` body `{"text"}`
- `POST /api/piyue` body `{"taskNo","subNo","verdict","opinion"}`
- `POST /api/plan-pause` body `{"paused":true|false}`
- `GET /api/queue` → 任务 + 子任务
- `GET /api/feed` → 消息流
- 鉴权头 `X-OPC-Token`；超时 5s；任何失败都不要抛到 UI，转成 `ResultData(offline=true)`。

## 7. 完成定义

`./gradlew :app:assembleDebug` 通过，产出 `app/build/outputs/apk/debug/app-debug.apk`；无编译警告级错误；无 TODO 占位符（演示数据除外）。
