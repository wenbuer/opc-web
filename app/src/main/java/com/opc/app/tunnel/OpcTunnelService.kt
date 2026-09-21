package com.opc.app.tunnel

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.opc.app.MainActivity
import com.opc.app.R
import com.wireguard.android.backend.GoBackend
import java.util.concurrent.CompletableFuture

/**
 * 隧道的前台壳。
 *
 * 官方 GoBackend 需要一个 VpnService 实例来拿 VpnService.Builder，而 Android 8 起
 * VpnService 又必须前台，所以这里两者合一：继承库自带的 GoBackend.VpnService
 * （它的 onCreate 会把实例登记进 GoBackend 的静态 CompletableFuture，GoBackend 随后
 * 用它建 tun / 装路由 / 起 wg）。
 *
 * 一个 App 只能声明一个 VPN 服务，否则 VpnService.prepare() 无法确定把授权发给谁；
 * 因此 manifest 里把库自带的那个声明移除，由这一个顶上。
 */
class OpcTunnelService : GoBackend.VpnService() {

    override fun onCreate() {
        // 先 super：库的 onCreate 会把 this 登记给 GoBackend，TunnelController 随后才等得到
        super.onCreate()
        started.complete(Unit)
        goForeground()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // 服务还活着时再 start 一次不会再走 onCreate，这里补一次信号
        started.complete(Unit)
        goForeground()
        return super.onStartCommand(intent, flags, startId)
    }

    override fun onDestroy() {
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun goForeground() {
        val manager = getSystemService(NotificationManager::class.java) ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && manager.getNotificationChannel(CHANNEL_ID) == null) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "隧道", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "保持 OPC 隧道在线"
                    setShowBadge(false)
                },
            )
        }
        val open = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("OPC 隧道已连接")
            .setContentText("只有服务端隧道地址走隧道，其余流量照旧")
            .setOngoing(true)
            .setShowWhen(false)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(open)
            .build()
        // 后台起前台服务在 Android 12+ 会被系统拒；拿不到通知也继续跑，不回滚隧道
        runCatching {
            ServiceCompat.startForeground(
                this,
                NOTIFICATION_ID,
                notification,
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
                } else {
                    0
                },
            )
        }
    }

    companion object {
        private const val CHANNEL_ID = "opc_tunnel"
        private const val NOTIFICATION_ID = 8902

        /** 服务起来（onCreate/onStartCommand）时被唤醒；TunnelController 在 startService 前登记。 */
        @Volatile
        internal var started: CompletableFuture<Unit> = CompletableFuture()

        /** 发起 startForegroundService 之前先登记信号；onCreate/onStartCommand 会唤醒它。 */
        fun expectStart(): CompletableFuture<Unit> {
            val signal = CompletableFuture<Unit>()
            started = signal
            return signal
        }

        fun startIntent(context: Context): Intent = Intent(context, OpcTunnelService::class.java)
    }
}
