package com.opc.app

import android.app.Application
import com.opc.app.tunnel.TunnelController

class OpcApplication : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        // 隧道门面在进程内只装配一次；未装配时状态停在 IDLE，不会碰 VPN
        TunnelController.install(this, container.settingsStore)
    }
}
