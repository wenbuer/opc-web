package com.opc.app.data.remote

import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

/**
 * 服务端地址可在运行期变化（重新扫码 / 换房间），所以按 baseUrl 缓存 Retrofit 实例，
 * 换地址只重建一次，不做全局单例锁死。
 */
object NetworkFactory {

    val json: Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        explicitNulls = false
        encodeDefaults = true
    }

    /** 鉴权头来源：仓库在配对信息变化时同步进来，避免每个请求都去读 DataStore。 */
    @Volatile
    var token: String? = null

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .writeTimeout(8, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .addInterceptor { chain ->
                val request = chain.request()
                val current = token
                val authed = if (current.isNullOrBlank()) {
                    request
                } else {
                    request.newBuilder().header("X-OPC-Token", current).build()
                }
                chain.proceed(authed)
            }
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BASIC
            })
            .build()
    }

    private val cache = HashMap<String, OpcApi>()

    @Synchronized
    fun api(baseUrl: String): OpcApi = cache.getOrPut(baseUrl.trimEnd('/')) {
        Retrofit.Builder()
            .baseUrl(baseUrl.trimEnd('/') + "/")
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(OpcApi::class.java)
    }
}
