# -*- coding: utf-8 -*-
"""DshEngine：DeepSeek Harness 的 headless profile。

阶段 1 说明：dsh 的实现暂寄在 runner.py（_spawn_headless / 会话日志心跳 / 用量抽取），
本模块先做**接口适配**——把 runner 的既有实现包成统一引擎，使上层（chain/scheduler/server）
与「引擎是谁」彻底解耦。阶段 2 把实现整体搬进本模块，届时 runner 只留事件流。

循环依赖处理：本模块在**函数内**导入 runner（runner 顶层会导入 engines 取引擎）。
"""
from .base import Engine, EngineError, Progress, RunResult


class DshEngine(Engine):
    name = "dsh"
    label = "DSH（DeepSeek Harness）"
    description = "调用 dsh headless 执行，自带工具沙箱与技能生态；进度取自会话日志"
    def capabilities(self) -> dict:
        return {"tools": True, "streaming": True, "usage": True, "skills": True, "sandbox": True}

    def preflight(self):
        from .. import runner
        cmd = runner._dsh_command()
        if not cmd:
            return False, "未找到 dsh 命令：请安装 @deepseek-ai/dsh，或把其 bin 目录加入 PATH"
        return True, "dsh 命令可用：" + " ".join(str(x) for x in cmd[:2])

    def run(self, prompt: str, *, timeout: float = 600, act: str = "",
            cwd=None, on_progress=None) -> RunResult:
        from .. import runner
        import time
        t0 = time.monotonic()
        try:
            text, usage, session = runner._run_prompt_dsh(prompt, timeout, act, on_progress)
        except Exception as e:                      # 启动失败/编码异常等
            return RunResult(error="dsh 执行异常：%s" % e, elapsed=time.monotonic() - t0)
        return RunResult(text=text or "", usage=usage, session=session or "",
                         elapsed=time.monotonic() - t0)

    def kill(self, act: str) -> bool:
        from .. import runner
        return bool(runner._kill_spawn(act))
