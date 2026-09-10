# -*- coding: utf-8 -*-
"""执行引擎包：控制台通过统一接口调用「谁在执行角色任务」。

    chain / scheduler / server
            │  只依赖 runner 的既有签名
            ▼
        runner.py               事件缓冲 + 执行状态 + 薄包装
            │  get_engine()
            ▼
        engines/                Engine 接口（base）+ 实现（dsh / api / …）+ 注册表

切引擎改配置即可（opc-config.json 的 "engine"，或环境变量 OPC_ENGINE）。
"""
from .base import Engine, EngineError, Progress, RunResult  # noqa: F401
from .registry import available, describe, get_engine, load_errors, register  # noqa: F401
