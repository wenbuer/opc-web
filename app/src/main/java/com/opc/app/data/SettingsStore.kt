package com.opc.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.opc.app.domain.ProjectInfo
import com.opc.app.domain.ServerConfig
import com.opc.app.domain.TunnelProfile
import com.opc.app.tunnel.WireGuardConfig
import com.opc.app.ui.theme.ThemeMode
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.opcDataStore: DataStore<Preferences> by preferencesDataStore(name = "opc_settings")

/** 配对信息、演示模式开关与离线缓存都落本机 DataStore；token 不出设备。 */
class SettingsStore(private val context: Context) {

    val config: Flow<ServerConfig?> = context.opcDataStore.data.map { prefs ->
        val url = prefs[KEY_BASE_URL] ?: return@map null
        ServerConfig(
            baseUrl = url,
            token = prefs[KEY_TOKEN].orEmpty(),
            deviceCode = prefs[KEY_DEVICE_CODE].orEmpty(),
            deviceName = prefs[KEY_DEVICE_NAME].orEmpty(),
            serverVersion = prefs[KEY_SERVER_VERSION].orEmpty(),
            pairedAt = prefs[KEY_PAIRED_AT] ?: 0L,
        )
    }

    val project: Flow<ProjectInfo?> = context.opcDataStore.data.map { prefs ->
        val id = prefs[KEY_PROJECT_ID] ?: return@map null
        ProjectInfo(
            id = id,
            name = prefs[KEY_PROJECT_NAME].orEmpty(),
            roleCount = prefs[KEY_PROJECT_ROLES] ?: 0,
            runningSubtasks = prefs[KEY_PROJECT_RUNNING] ?: 0,
        )
    }

    /** 演示模式：没服务端也能进主界面看全部页面（顶栏会挂「演示数据」标记）。 */
    val demoMode: Flow<Boolean> = context.opcDataStore.data.map { it[KEY_DEMO_MODE] ?: false }

    /** 主题模式：设备级偏好，与配对无关，clearPairing 不碰它。 */
    val themeMode: Flow<ThemeMode> = context.opcDataStore.data.map { ThemeMode.fromKey(it[KEY_THEME_MODE]) }

    suspend fun saveThemeMode(mode: ThemeMode) {
        context.opcDataStore.edit { prefs -> prefs[KEY_THEME_MODE] = mode.key }
    }

    /**
     * 隧道档案（含手机侧私钥）。私钥只在手机生成、只落应用私有目录，任何时候都不上传；
     * 没配过隧道（老二维码 / 演示模式）时为 null。
     */
    val tunnelProfile: Flow<TunnelProfile?> = context.opcDataStore.data.map { prefs ->
        val privateKey = prefs[KEY_WG_PRIVATE] ?: return@map null
        TunnelProfile(
            privateKey = privateKey,
            publicKey = prefs[KEY_WG_PUBLIC].orEmpty(),
            peerPublicKey = prefs[KEY_WG_PEER].orEmpty(),
            endpoint = prefs[KEY_WG_ENDPOINT].orEmpty(),
            address = prefs[KEY_WG_ADDRESS].orEmpty(),
            allowedIps = prefs[KEY_WG_ALLOWED].orEmpty(),
            mtu = prefs[KEY_WG_MTU] ?: WireGuardConfig.DEFAULT_MTU,
            dns = prefs[KEY_WG_DNS],
            keepalive = prefs[KEY_WG_KEEPALIVE],
        )
    }

    suspend fun currentTunnelProfile(): TunnelProfile? = tunnelProfile.first()

    /** 设备确认状态：false 表示服务端还没放行写接口，界面上要留一个重试入口。 */
    val deviceConfirmed: Flow<Boolean> = context.opcDataStore.data.map { it[KEY_DEVICE_CONFIRMED] ?: true }

    suspend fun currentDeviceConfirmed(): Boolean = deviceConfirmed.first()

    suspend fun saveDeviceConfirmed(confirmed: Boolean) {
        context.opcDataStore.edit { prefs -> prefs[KEY_DEVICE_CONFIRMED] = confirmed }
    }

    suspend fun saveTunnelProfile(profile: TunnelProfile) {
        context.opcDataStore.edit { prefs ->
            prefs[KEY_WG_PRIVATE] = profile.privateKey
            prefs[KEY_WG_PUBLIC] = profile.publicKey
            prefs[KEY_WG_PEER] = profile.peerPublicKey
            prefs[KEY_WG_ENDPOINT] = profile.endpoint
            prefs[KEY_WG_ADDRESS] = profile.address
            prefs[KEY_WG_ALLOWED] = profile.allowedIps
            prefs[KEY_WG_MTU] = profile.mtu
            profile.dns?.let { prefs[KEY_WG_DNS] = it } ?: prefs.remove(KEY_WG_DNS)
            profile.keepalive?.let { prefs[KEY_WG_KEEPALIVE] = it } ?: prefs.remove(KEY_WG_KEEPALIVE)
        }
    }

    suspend fun currentConfig(): ServerConfig? = config.first()

    suspend fun isDemoMode(): Boolean = demoMode.first()

    suspend fun savePairing(config: ServerConfig) {
        context.opcDataStore.edit { prefs ->
            prefs[KEY_BASE_URL] = config.baseUrl
            prefs[KEY_TOKEN] = config.token
            prefs[KEY_DEVICE_CODE] = config.deviceCode
            prefs[KEY_DEVICE_NAME] = config.deviceName
            prefs[KEY_SERVER_VERSION] = config.serverVersion
            prefs[KEY_PAIRED_AT] = config.pairedAt
            prefs[KEY_DEMO_MODE] = false
        }
    }

    /** 体验演示：写一条占位配置，让根 Composable 认为已就绪。 */
    suspend fun enableDemoMode() {
        context.opcDataStore.edit { prefs ->
            prefs[KEY_BASE_URL] = DEMO_BASE_URL
            prefs[KEY_TOKEN] = DEMO_TOKEN
            prefs[KEY_DEVICE_CODE] = "DEV-DEMO-0001"
            prefs[KEY_DEVICE_NAME] = "本机演示"
            prefs[KEY_SERVER_VERSION] = "演示模式"
            prefs[KEY_PAIRED_AT] = System.currentTimeMillis()
            prefs[KEY_DEMO_MODE] = true
            prefs[KEY_PROJECT_ID] = "opc-app"
            prefs[KEY_PROJECT_NAME] = "OPC-APP"
            prefs[KEY_PROJECT_ROLES] = 4
            prefs[KEY_PROJECT_RUNNING] = 3
        }
    }

    suspend fun saveProject(project: ProjectInfo) {
        context.opcDataStore.edit { prefs ->
            prefs[KEY_PROJECT_ID] = project.id
            prefs[KEY_PROJECT_NAME] = project.name
            prefs[KEY_PROJECT_ROLES] = project.roleCount
            prefs[KEY_PROJECT_RUNNING] = project.runningSubtasks
        }
    }

    suspend fun saveCache(key: String, json: String) {
        context.opcDataStore.edit { prefs ->
            prefs[stringPreferencesKey(CACHE_PREFIX + key)] = json
            prefs[longPreferencesKey(CACHE_TIME_PREFIX + key)] = System.currentTimeMillis()
        }
    }

    suspend fun readCache(key: String): String? =
        context.opcDataStore.data.first()[stringPreferencesKey(CACHE_PREFIX + key)]

    /**
     * 解除配对：配对、项目、缓存、演示开关全清，避免下次进来看到旧数据。
     * 刻意不清 KEY_THEME_MODE —— 深浅是这台设备的外观偏好，跟配对的是哪台服务端没关系。
     */
    suspend fun clearPairing() {
        context.opcDataStore.edit { prefs ->
            prefs.asMap().keys
                .filter { it.name.startsWith(CACHE_PREFIX) || it.name.startsWith(CACHE_TIME_PREFIX) }
                .forEach { key -> prefs.remove(key) }
            prefs.remove(KEY_BASE_URL)
            prefs.remove(KEY_TOKEN)
            prefs.remove(KEY_DEVICE_CODE)
            prefs.remove(KEY_SERVER_VERSION)
            prefs.remove(KEY_PAIRED_AT)
            prefs.remove(KEY_PROJECT_ID)
            prefs.remove(KEY_PROJECT_NAME)
            prefs.remove(KEY_PROJECT_ROLES)
            prefs.remove(KEY_PROJECT_RUNNING)
            prefs.remove(KEY_DEMO_MODE)
            prefs.remove(KEY_DEVICE_CONFIRMED)
            // 解配对同时销毁隧道身份：私钥留着等于把上一台服务端的通道留在手机里
            prefs.remove(KEY_WG_PRIVATE)
            prefs.remove(KEY_WG_PUBLIC)
            prefs.remove(KEY_WG_PEER)
            prefs.remove(KEY_WG_ENDPOINT)
            prefs.remove(KEY_WG_ADDRESS)
            prefs.remove(KEY_WG_ALLOWED)
            prefs.remove(KEY_WG_MTU)
            prefs.remove(KEY_WG_DNS)
            prefs.remove(KEY_WG_KEEPALIVE)
        }
    }

    companion object {
        const val DEMO_BASE_URL = "demo://local"
        const val DEMO_TOKEN = "demo"
        private const val CACHE_PREFIX = "cache_"
        private const val CACHE_TIME_PREFIX = "cache_at_"
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        private val KEY_TOKEN = stringPreferencesKey("token")
        private val KEY_DEVICE_CODE = stringPreferencesKey("device_code")
        private val KEY_DEVICE_NAME = stringPreferencesKey("device_name")
        private val KEY_SERVER_VERSION = stringPreferencesKey("server_version")
        private val KEY_PAIRED_AT = longPreferencesKey("paired_at")
        private val KEY_PROJECT_ID = stringPreferencesKey("project_id")
        private val KEY_PROJECT_NAME = stringPreferencesKey("project_name")
        private val KEY_PROJECT_ROLES = intPreferencesKey("project_roles")
        private val KEY_PROJECT_RUNNING = intPreferencesKey("project_running")
        private val KEY_DEMO_MODE = booleanPreferencesKey("demo_mode")
        private val KEY_THEME_MODE = stringPreferencesKey("theme_mode")
        private val KEY_DEVICE_CONFIRMED = booleanPreferencesKey("device_confirmed")
        private val KEY_WG_PRIVATE = stringPreferencesKey("wg_private_key")
        private val KEY_WG_PUBLIC = stringPreferencesKey("wg_public_key")
        private val KEY_WG_PEER = stringPreferencesKey("wg_peer_public_key")
        private val KEY_WG_ENDPOINT = stringPreferencesKey("wg_endpoint")
        private val KEY_WG_ADDRESS = stringPreferencesKey("wg_address")
        private val KEY_WG_ALLOWED = stringPreferencesKey("wg_allowed_ips")
        private val KEY_WG_MTU = intPreferencesKey("wg_mtu")
        private val KEY_WG_DNS = stringPreferencesKey("wg_dns")
        private val KEY_WG_KEEPALIVE = intPreferencesKey("wg_keepalive")
    }
}
