# -*- coding: utf-8 -*-
"""ApiEngine：直连大模型 API 的 agent 循环（不依赖 dsh）。

设计（见 docs/引擎解耦设计.md 阶段 2）：
- 只用标准库（urllib）发流式请求，不引入 HTTP 依赖；
- 模型通过工具调用读写文件、跑命令，循环直到给出最终文本；
- 流式增量直接喂给 on_progress，所以进度是**真流式**的（dsh 那边靠会话日志轮询）；
- 用量取 API 返回的 usage（与 dsh 口径对齐：input 含 cache 命中另存）。

工具与沙箱：全部路径先 resolve 再校验必须落在项目根内；命令在项目根下执行并设超时。
"""
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .base import Engine, EngineError, Progress, RunResult

_DEFAULTS = {
    "baseUrl": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "apiKeyEnv": "DEEPSEEK_API_KEY",
    "maxSteps": 40,          # 工具循环上限（防死循环烧钱）
    "temperature": 0.3,
    "maxTokens": 8192,
    "commandTimeout": 300,   # 单条命令超时（秒）
}
_CANCEL = {}                 # act -> True（kill() 置位，循环内检查）
_RUNNING = set()             # 正在跑的 act（kill 据此回答「现在是否真的有在跑」）
_CANCEL_LOCK = threading.Lock()

SYSTEM_PROMPT = """你是 OPC 项目里的执行角色，在项目根目录内独立完成任务。

工作方式：
- 先用 list_dir / read_file 搞清楚现状，不要凭空假设文件内容；
- 产出用 write_file 落盘（路径相对项目根，用 / 分隔）；
- 需要验证就跑 run_command（在项目根下执行，给出命令与期望）；
- 做完后用**纯文本**给出最终回报正文（会作为该子任务的回报文件内容），
  包含：完成了什么 / 产出文件路径 / 关键结论 / 没做完或需要 R0 拍板的事项。
  不要输出 JSON，不要复述这份说明。"""

TOOLS = [
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "列出目录内容（相对项目根）。默认列出项目根。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "相对路径，如 工作区/全栈开发"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取文本文件内容（相对项目根）。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "max_chars": {"type": "integer", "description": "最多读取字符数，默认 20000"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "写入文本文件（相对项目根）；目录不存在会自动创建。整文件覆盖。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "在项目根目录执行一条 PowerShell 命令并返回输出。",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}},
            "required": ["command"]}}},
]


def _cfg() -> dict:
    """引擎配置：沿用「设置 → 模型接入」，再用 opc-config.json 的 engines.api 段覆盖。

    模型接入页写的 provider / apiKeyEnv / baseURL / model 就是「用哪个模型」，
    api 引擎必须读同一份 —— 否则界面选了自定义提供方，引擎还去打默认端点。
    engines.api 段（可选）只用于按引擎单独覆盖，如给执行单独配更便宜的模型。"""
    from .. import config
    cfg = dict(_DEFAULTS)
    try:                                        # 先取模型接入的配置打底
        mi = config.model_info()
        for src, dst in (("baseURL", "baseUrl"), ("model", "model"), ("apiKeyEnv", "apiKeyEnv")):
            if mi.get(src):
                cfg[dst] = mi[src]
    except Exception:
        pass
    try:
        raw = (config._CFG.get("engines") or {}).get("api") or {}
    except Exception:
        raw = {}
    cfg.update({k: v for k, v in raw.items() if v not in (None, "")})
    cfg["baseUrl"] = str(cfg["baseUrl"]).rstrip("/")
    return cfg


def _api_key(cfg: dict) -> str:
    from .. import config
    env = config.read_env_file() if hasattr(config, "read_env_file") else {}
    key = os.environ.get(cfg["apiKeyEnv"]) or env.get(cfg["apiKeyEnv"]) or ""
    return str(key).strip()


def _root() -> Path:
    from .. import config
    return Path(config.ROOT)


def _safe_path(rel: str) -> Path:
    """把相对路径解析到项目根内；越界或绝对路径一律拒绝。"""
    root = _root().resolve()
    p = (root / str(rel or ".").replace("\\", "/")).resolve()
    if p != root and root not in p.parents:
        raise ValueError("路径越出项目根：%s" % rel)
    return p


def _t_list_dir(args: dict) -> str:
    p = _safe_path(args.get("path") or ".")
    if not p.is_dir():
        return "不是目录：%s" % args.get("path")
    rows = []
    for e in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if e.name in (".git", "__pycache__", "node_modules"):
            continue
        rows.append(("%s/" % e.name) if e.is_dir() else "%s  (%d B)" % (e.name, e.stat().st_size))
    return "\n".join(rows[:200]) or "（空目录）"


def _t_read_file(args: dict) -> str:
    p = _safe_path(args.get("path"))
    if not p.is_file():
        return "文件不存在：%s" % args.get("path")
    n = int(args.get("max_chars") or 20000)
    return p.read_text(encoding="utf-8", errors="replace")[:n]


def _t_write_file(args: dict) -> str:
    p = _safe_path(args.get("path"))
    p.parent.mkdir(parents=True, exist_ok=True)
    text = str(args.get("content") or "")
    p.write_text(text, encoding="utf-8")
    return "已写入 %s（%d 字符）" % (args.get("path"), len(text))


def _t_run_command(args: dict) -> str:
    cfg = _cfg()
    cmd = str(args.get("command") or "").strip()
    if not cmd:
        return "命令为空"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           cwd=str(_root()), capture_output=True, text=True,
                           timeout=float(cfg["commandTimeout"]), encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "命令超时（%ss）：%s" % (cfg["commandTimeout"], cmd)
    except Exception as e:
        return "命令执行异常：%s" % e
    out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if (r.stderr or "").strip() else "")
    return ("exit=%d\n%s" % (r.returncode, out.strip()))[:8000]


_TOOL_IMPL = {"list_dir": _t_list_dir, "read_file": _t_read_file,
              "write_file": _t_write_file, "run_command": _t_run_command}


def _stream_chat(cfg: dict, messages: list, on_delta=None, cancel=None) -> dict:
    """流式请求一轮，返回 {text, tool_calls, usage, finish}。

    标准库 SSE 解析：逐行读 data: 行，累积 content 与 tool_calls 分片。
    """
    key = _api_key(cfg)
    if not key:
        raise EngineError("未配置 API Key：请设置环境变量 %s（或写入项目 .env）" % cfg["apiKeyEnv"])
    payload = {"model": cfg["model"], "messages": messages, "tools": TOOLS,
               "stream": True, "stream_options": {"include_usage": True},
               "temperature": float(cfg["temperature"]), "max_tokens": int(cfg["maxTokens"])}
    req = urllib.request.Request(
        cfg["baseUrl"] + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST")
    out = {"text": "", "tool_calls": [], "usage": None, "finish": ""}
    calls = {}
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            if cancel is not None and cancel():
                out["finish"] = "cancelled"
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk == "[DONE]":
                break
            try:
                d = json.loads(chunk)
            except Exception:
                continue
            if d.get("usage"):
                u = d["usage"] or {}
                out["usage"] = {"inputTokens": int(u.get("prompt_tokens") or 0),
                                "outputTokens": int(u.get("completion_tokens") or 0),
                                "cacheReadTokens": int(u.get("prompt_cache_hit_tokens") or 0),
                                "reasoningTokens": int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)}
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                if ch.get("finish_reason"):
                    out["finish"] = str(ch["finish_reason"])
                piece = delta.get("content")
                if piece:
                    out["text"] += piece
                    if on_delta:
                        on_delta(piece)
                for tc in delta.get("tool_calls") or []:
                    i = int(tc.get("index") or 0)
                    slot = calls.setdefault(i, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
    out["tool_calls"] = [calls[k] for k in sorted(calls)]
    return out


class ApiEngine(Engine):
    name = "api"
    label = "直连大模型 API"
    description = "内置 4 个工具的 agent 循环，直连 API 流式执行；不依赖 dsh"
    def capabilities(self) -> dict:
        return {"tools": True, "streaming": True, "usage": True, "skills": False, "sandbox": True}

    def preflight(self):
        cfg = _cfg()
        if not _api_key(cfg):
            return False, "未配置 API Key（环境变量 %s）" % cfg["apiKeyEnv"]
        return True, "API 引擎就绪：%s · %s" % (cfg["model"], cfg["baseUrl"])

    def kill(self, act: str) -> bool:
        """终止 act 上的运行；返回「现在是否真的有在跑」。

        取消标志先置位（run 还没开始就 kill 也生效，清理时机见 run 内的注释），
        返回值只表示当前确有运行 —— 多引擎共存/按用途路由时，上层靠它判断该找谁终止。"""
        if not act:
            return False
        with _CANCEL_LOCK:
            _CANCEL[act] = True
            return act in _RUNNING

    def run(self, prompt: str, *, timeout: float = 600, act: str = "",
            cwd=None, on_progress=None) -> RunResult:
        cfg = _cfg()
        t0 = time.monotonic()
        deadline = t0 + float(timeout or 600)
        # 注意：这里**不能**清取消标志——kill() 可能在 run() 之前被调用（删除任务/超时），
        # 清掉就等于把取消吞了。标志由 finally 在本次运行结束时清理，保证不残留到下次。

        if act:
            with _CANCEL_LOCK:
                _RUNNING.add(act)

        def cancelled() -> bool:
            with _CANCEL_LOCK:
                return bool(_CANCEL.get(act)) or time.monotonic() > deadline

        steps = 0
        n_tools = 0
        last_tool = ""
        last_text = ""
        last_beat = 0.0
        usage_total = {"inputTokens": 0, "outputTokens": 0, "cacheReadTokens": 0, "reasoningTokens": 0}
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}]

        def beat(last_tool_arg="", last_text_arg="", force=False):
            nonlocal last_beat, last_tool, last_text
            if last_tool_arg:
                last_tool = last_tool_arg
            if last_text_arg:
                last_text = last_text_arg
            now = time.monotonic()
            if not force and now - last_beat < 1.0:      # 节流：进度最多每秒一次
                return
            last_beat = now
            if on_progress:
                on_progress(Progress(alive=True, elapsed=int(now - t0), tools=n_tools,
                                     lastTool=last_tool, lastText=last_text[:120]))

        try:
            while steps < int(cfg["maxSteps"]):
                if cancelled():
                    with _CANCEL_LOCK:
                        _CANCEL.pop(act, None)
                    return RunResult(text=last_text, usage=usage_total, elapsed=time.monotonic() - t0,
                                     killed=True, error="已取消或超时")
                steps += 1
                buf = []
                r = _stream_chat(cfg, messages, on_delta=lambda p: (buf.append(p), beat("", "".join(buf)[-120:])),
                                 cancel=cancelled)
                if r.get("usage"):
                    for k in usage_total:
                        usage_total[k] += int(r["usage"].get(k) or 0)
                text = r.get("text") or ""
                if text.strip():
                    last_text = " ".join(text.split())[:200]
                if r.get("tool_calls"):
                    messages.append({"role": "assistant", "content": text or None,
                                     "tool_calls": [{"id": c["id"] or ("call_%d" % i), "type": "function",
                                                     "function": {"name": c["name"], "arguments": c["arguments"]}}
                                                    for i, c in enumerate(r["tool_calls"])]})
                    for i, c in enumerate(r["tool_calls"]):
                        name = c["name"]
                        try:
                            args = json.loads(c["arguments"] or "{}")
                        except Exception:
                            args = {}
                        n_tools += 1
                        beat((name + " " + json.dumps(args, ensure_ascii=False))[:130], "", force=True)
                        impl = _TOOL_IMPL.get(name)
                        try:
                            result = impl(args) if impl else "未知工具：%s" % name
                        except Exception as e:
                            result = "工具执行失败：%s" % e
                        messages.append({"role": "tool", "tool_call_id": c["id"] or ("call_%d" % i),
                                         "content": str(result)[:12000]})
                    continue
                # 没有工具调用 → 结束
                beat(force=True)
                return RunResult(text=text, usage=usage_total, session="api-%d" % steps,
                                 elapsed=time.monotonic() - t0)
            return RunResult(text=last_text, usage=usage_total, elapsed=time.monotonic() - t0,
                             error="达到工具循环上限 %d 步（疑似空转），已中止" % cfg["maxSteps"])
        except EngineError as e:
            return RunResult(error=str(e), elapsed=time.monotonic() - t0)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            return RunResult(error="API HTTP %s：%s" % (e.code, body), elapsed=time.monotonic() - t0)
        except Exception as e:
            return RunResult(error="API 引擎异常：%s" % e, elapsed=time.monotonic() - t0)
        finally:
            with _CANCEL_LOCK:
                _CANCEL.pop(act, None)
                _RUNNING.discard(act)
            if on_progress:      # 结束信号：不报的话上层状态会一直停在「执行中」
                on_progress(Progress(alive=False, finished=True,
                                     elapsed=int(time.monotonic() - t0)))
