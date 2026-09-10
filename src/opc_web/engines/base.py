# -*- coding: utf-8 -*-
"""执行引擎接口与数据类。

设计要点见 docs/引擎解耦设计.md：
- 引擎只负责「跑一次 prompt」，进度/用量/超时都通过统一结构回传；
- 事件流（emit/events）留在 runner，不属于引擎；
- 能力声明（capabilities）让控制台按引擎差异降级（无流式的引擎不显示进度行等）。
"""
from dataclasses import dataclass


@dataclass
class Progress:
    """一次运行的活动快照：有活动即视为存活（heartbeat 语义）。"""
    alive: bool = True
    elapsed: int = 0          # 已运行秒数
    tools: int = 0            # 工具调用次数
    lastTool: str = ""        # 最近一次工具（名称 + 参数摘要）
    lastText: str = ""        # 最近一段模型文本（单行、已压缩）
    session: str = ""         # 引擎侧的会话标识（dsh 给会话目录尾号；API 引擎给 request id）
    finished: bool = False    # 本次运行已结束：上层据此清掉「执行中」状态（引擎不直接碰上层状态）


@dataclass
class RunResult:
    """一次运行的最终结果。"""
    text: str = ""            # 最终文本（headless 语义：无文本即视为无产出）
    usage: dict | None = None  # {inputTokens, outputTokens, cacheReadTokens, reasoningTokens}
    session: str = ""
    elapsed: float = 0.0
    killed: bool = False      # 被超时/强杀终止
    error: str = ""           # 引擎级错误（启动失败、鉴权失败等）

    def ok(self) -> bool:
        return bool(str(self.text or "").strip()) and not self.error


class EngineError(RuntimeError):
    """引擎不可用或调用失败（配置错误、未注册、preflight 不通过）。"""


class Engine:
    """执行引擎基类：新引擎只需实现 run()，并按需覆盖其余方法。"""

    name = "base"
    label = "base"        # 设置页显示名
    description = ""      # 一句话说明（设置页与自检提示用）

    def capabilities(self) -> dict:
        """能力声明：控制台据此决定 UI 与提示词策略。"""
        return {"tools": False, "streaming": False, "usage": False, "skills": False, "sandbox": False}

    def preflight(self):
        """可用性自检 → (可用: bool, 说明: str)。启动/派发前调用，避免静默失败。"""
        return True, ""

    def run(self, prompt: str, *, timeout: float = 600, act: str = "",
            cwd=None, on_progress=None) -> RunResult:
        """跑一次任务。

        - act：子任务号，用于注册/终止运行（删除任务/超时强杀）
        - on_progress(Progress)：有活动时回调，控制台据此推进度行与心跳；
          **返回前必须再报一次 Progress(finished=True)**，否则上层会把这次运行
          一直当成「执行中」（状态残留）。
        """
        raise NotImplementedError("引擎未实现 run(): %s" % self.name)

    def kill(self, act: str) -> bool:
        """终止 act 对应的运行（返回是否真的终止了）。"""
        return False

    def skills(self) -> list:
        """该引擎可提供的可装配技能（无则空列表）。"""
        return []
