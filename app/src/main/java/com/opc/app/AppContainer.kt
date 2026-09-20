package com.opc.app

import android.content.Context
import com.opc.app.data.OpcRepository
import com.opc.app.data.OpcRepositoryImpl
import com.opc.app.data.SettingsStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

/** 手写依赖装配：初版只有一个仓库 + 一个设置存储，引 Hilt 不划算。 */
class AppContainer(context: Context) {

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    val settingsStore: SettingsStore = SettingsStore(context.applicationContext)

    val repository: OpcRepository = OpcRepositoryImpl(settingsStore, appScope)
}
