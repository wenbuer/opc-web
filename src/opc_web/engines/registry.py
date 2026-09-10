# -*- coding: utf-8 -*-
"""引擎注册表：按配置选择实现；名字不存在时**报错**而不是静默回退。

静默回退会掩盖配置错误（写错引擎名却以为切成功了），故明确抛 EngineError。
内置引擎导入失败同样记录在案并原样抛出 —— 曾经用 `except: pass` 吞掉，api.py 一旦
导入失败，引擎会凭空消失，只在切过去时才报「未注册」，排查要多绕一圈。
"""
import importlib
import os

from .base import Engine, EngineError

_ENGINES = {}
_LOAD_ERRORS = {}        # 名字 -> 导入失败原因（内置引擎）


def register(cls):
    """注册一个引擎实现（类级装饰器）。"""
    _ENGINES[cls.name] = cls
    return cls


def _load_builtins():
    if _ENGINES or _LOAD_ERRORS:
        return
    for mod, cls_name in (("dsh", "DshEngine"), ("api", "ApiEngine")):
        try:
            obj = importlib.import_module("." + mod, __package__)
            register(getattr(obj, cls_name))
        except Exception as e:
            _LOAD_ERRORS[mod] = "%s: %s" % (type(e).__name__, e)


def available() -> list:
    """已成功注册的引擎名。"""
    _load_builtins()
    return sorted(_ENGINES)


def load_errors() -> dict:
    """加载失败的内置引擎：{名字: 原因}。"""
    _load_builtins()
    return dict(_LOAD_ERRORS)


def get_engine(name: str = None) -> Engine:
    """取引擎实例。name 为空 → 用配置里的 engine（默认 api）。"""
    _load_builtins()
    if not name:
        from .. import config
        name = getattr(config, "ENGINE", "") or "api"
    want = str(name).strip().lower()
    cls = _ENGINES.get(want)
    if cls is None:
        if want in _LOAD_ERRORS:
            raise EngineError("执行引擎 %s 加载失败：%s" % (want, _LOAD_ERRORS[want]))
        raise EngineError("未注册的执行引擎：%s（可用：%s）" % (want, ", ".join(available()) or "无"))
    return cls()


def describe(name: str = None) -> dict:
    """引擎全景（设置页用）：当前是谁、能不能用、有什么能力、还能换成谁。"""
    _load_builtins()
    if not name:
        from .. import config
        name = getattr(config, "ENGINE", "") or "api"
    cur = str(name).strip().lower()
    items = []
    for n in available():
        eng = get_engine(n)
        try:
            ok, note = eng.preflight()
        except Exception as e:
            ok, note = False, "自检异常：%s" % e
        items.append({"name": n, "label": eng.label, "description": eng.description,
                      "current": n == cur, "ok": bool(ok), "note": note,
                      "capabilities": eng.capabilities()})
    return {"current": cur, "engines": items, "errors": load_errors(),
            # 设了 OPC_ENGINE 时它会盖掉设置页的选择，界面要说明白，否则「切了没反应」
            "envOverride": str(os.environ.get("OPC_ENGINE") or "").strip(),
            "ok": any(i["current"] and i["ok"] for i in items)}
