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

    /** 解除配对：配对、项目、缓存、演示开关全清，避免下次进来看到旧数据。 */
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
    }
}
