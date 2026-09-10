# -*- coding: utf-8 -*-
"""引擎注册表：按配置选择实现；名字不存在时报错而不是静默回退。

静默回退会掩盖配置错误（写错引擎名却以为切成功了），故明确抛 EngineError。
"""
from .base import Engine, EngineError

_ENGINES = {}


def register(cls):
    """注册一个引擎实现（类级装饰器）。"""
    _ENGINES[cls.name] = cls
    return cls


def _load_builtins():
    if _ENGINES:
        return
    from .dsh import DshEngine
    register(DshEngine)
    try:                                  # 阶段 2：API 引擎就位后自动可用
        from .api import ApiEngine
        register(ApiEngine)
    except Exception:
        pass


def available() -> list:
    _load_builtins()
    return sorted(_ENGINES)


def get_engine(name: str = None) -> Engine:
    """取引擎实例。name 为空 → 用配置的 engine（默认 dsh）。"""
    _load_builtins()
    if not name:
        from .. import config
        name = getattr(config, "ENGINE", "") or "dsh"
    want = str(name).strip().lower()
    cls = _ENGINES.get(want)
    if cls is None:
        raise EngineError("未注册的执行引擎：%s（可用：%s）" % (want, ", ".join(available())))
    return cls()
