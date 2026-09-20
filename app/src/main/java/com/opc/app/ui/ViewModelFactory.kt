package com.opc.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.opc.app.data.OpcRepository
import com.opc.app.data.SettingsStore

/**
 * 单工厂承载全部 ViewModel：构造签名只允许 (OpcRepository) 或 (OpcRepository, SettingsStore)。
 * 屏一多就为每屏手写工厂不划算，参数按类型精确匹配后反射构造。
 */
class OpcViewModelFactory(
    private val repository: OpcRepository,
    private val settingsStore: SettingsStore,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        val ctor = modelClass.constructors.firstOrNull { candidate ->
            val types = candidate.parameterTypes
            types.size in 1..2 && types.all { it == OpcRepository::class.java || it == SettingsStore::class.java }
        } ?: error("ViewModel " + modelClass.simpleName + " 的构造必须是 (OpcRepository) 或 (OpcRepository, SettingsStore)")

        val args: Array<Any> =
            if (ctor.parameterTypes.size == 2) arrayOf(repository, settingsStore)
            else arrayOf(repository)

        return ctor.newInstance(*args) as T
    }
}
