package com.opc.app.data

/**
 * 一次取数的结果。offline = true 表示拿的是本地演示/缓存数据而不是服务端的。
 * 任何网络异常都不该抛到 UI，统一在这里收口。
 */
data class ResultData<T>(
    val data: T,
    val offline: Boolean = false,
    val cachedAt: Long? = null,
    val error: String? = null,
) {
    fun map(transform: (T) -> T): ResultData<T> = copy(data = transform(data))
}

/** 与服务端的连接态，供顶栏与离线提示条用。 */
enum class LinkState { UNPAIRED, CONNECTING, ONLINE, OFFLINE }
