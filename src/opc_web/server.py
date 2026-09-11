# -*- coding: utf-8 -*-
"""HTTP 服务：路由与请求处理（标准库 http.server，零第三方依赖）。

每个端点 = 一个"产生响应 dict"的函数，交给 _ok() 统一输出：
成功 → JSON；ApiError → 其状态码；其它异常 → err（默认 500）。"""
import json
import os
import re
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote

from . import (assistant, bootstrap, chain, config, engines, knowledge, parsers, review, roles,
               runner, scheduler, skills, store, templates)


def _strip_okf_frontmatter(text: str) -> str:
    """剥离 OKF 文档开头的 YAML front-matter（供渲染，正文从第二个 '---' 后开始）。"""
    if text.startswith("---\n") or text.startswith("---\r\n"):
        for sep in ("\n---\n", "\n---\r\n"):
            end = text.find(sep, 3)
            if end > 0:
                return text[end + len(sep):]
    return text


class ApiError(Exception):
    """带 HTTP 状态码的业务错误；msg 即回给前端的 msg。"""

    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def _split_skills(v):
    """body['skills']（textarea 文本）→ 技能名列表；None=未提交该字段。

    每行一项，兼容「- xxx」列表写法；跳过空行与以 （ / ( 开头的提示行。"""
    if v is None:
        return None
    out = []
    for ln in str(v).splitlines():
        s = ln.strip()
        if s.startswith("- "):
            s = s[2:].strip()
        if s and not (s.startswith("（") or s.startswith("(")):
            out.append(s)
    return out


def _split_tags(v):
    """body['tags']（空格/逗号分隔字符串 或 数组）→ 标签列表；None=未提交（edit 保留现卡标签）。"""
    if v is None:
        return None
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [t for t in re.split(r"[\s,，、;；]+", str(v).strip()) if t]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _body(self):
        """读取 POST body 并解析 JSON；空 body 返回 {}；解析失败返回 None。"""
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return None

    def _qs(self):
        return parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, p, ctype):
        try:
            data = p.read_bytes()
        except OSError:
            self.send_error(404, "Not Found")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_html(self, q):
        """把项目/工作区里的 .html 作为 text/html 直接 serve（供预览 iframe 内嵌打开）。"""
        rel = unquote((q.get("rel") or [""])[0]).strip()
        if not rel:
            raise ApiError(400, "缺少文件路径")
        p = (config.ROOT / rel).resolve()
        if not str(p).startswith(str(config.ROOT.resolve())) or not p.is_file() or p.suffix.lower() != ".html":
            raise ApiError(404, "文件不存在或非 html")
        self._file(p, "text/html; charset=utf-8")

    def _ok(self, fn, err=500):
        """统一输出端点响应：fn 返回 dict → JSON；ApiError 按其状态码；其它异常按 err。"""
        try:
            self._json(fn())
        except ApiError as e:
            self._json({"ok": False, "msg": str(e)}, e.status)
        except Exception as e:
            self._json({"ok": False, "msg": str(e)}, err)

    # ---------- 只读端点 ----------
    def _get_md(self):
        rel = unquote(self._qs().get("rel", [""])[0])
        return {"ok": True, "rel": rel, "text": _strip_okf_frontmatter(knowledge.read_md(rel))}

    def _queue_rows(self):
        """任务队列（**最新在前**）：刚下达的任务排在最上面，不用翻到列表底部找。

        台账仍按任务号升序存放（分配新号依赖这个顺序），这里只翻转展示顺序；
        前端各处都是按 no 查找/计数，不依赖数组顺序。"""
        return list(reversed(store.tasks()))

    def _get_pending(self):
        data = parsers.parse_piyuetai(knowledge.read_md(config.PIYUETAI_REL))
        return {"ok": True, "work": data["work"], "pending": data["pending"],
                "archive": data["archive"]}

    def _get_summary(self):
        data = parsers.parse_piyuetai(knowledge.read_md(config.PIYUETAI_REL))
        return {"ok": True, "pendingCount": len(data["pending"]),
                "workCount": len(data["work"]), "archiveCount": len(data["archive"])}

    def _get_ws_file(self):
        rel = unquote(self._qs().get("rel", [""])[0]).strip()
        if not rel:
            raise ApiError(400, "缺少文件路径")
        return {"ok": True, **scheduler.ws_read(rel)}

    def _get_task_output(self):
        no = unquote(self._qs().get("no", [""])[0]).strip()
        if not no:
            raise ApiError(400, "缺少任务编号 no")
        return {"ok": True, **scheduler.task_output(no)}

    def _get_sub_output(self):
        no = unquote(self._qs().get("no", [""])[0]).strip()
        if not no:
            raise ApiError(400, "缺少子任务编号 no")
        res = scheduler.sub_output(no)
        if not res:
            raise ApiError(404, "未找到子任务产出 " + no)
        return {"ok": True, "no": no, **res}

    def _get_role_card(self):
        no = unquote(self._qs().get("no", [""])[0])
        p = config.AGENTS_DIR / (no + ".role.md")
        if not p.exists():
            raise ApiError(404, "角色不存在")
        return {"ok": True, "no": no, "card": config.read_text(p)}

    def _get_skill_lib(self):
        """共享技能库清单：agents/skills/ 下的技能文件名（装配时勾选，不手写）。"""
        d = config.AGENTS_DIR / config.SKILLS_REL
        names = sorted(p.name for p in d.glob("*.md")) if d.is_dir() else []
        return {"ok": True, "skills": names, "dir": str(d)}

    def _get_skill_sources(self):
        """可导入的技能（扫本机技能源）：**与当前引擎无关** —— 技能是项目资产，不是引擎能力。

        技能 md 导入后进共享技能库 agents/skills/，角色卡登记装配，执行时由
        agent_prompt() 把技能清单与路径注入 prompt、正文由角色按需读，所以两套引擎
        用的是同一份技能。引擎的差别只在 capabilities.skills：技能里那些「跑命令 /
        读写文件」的步骤，dsh 自带工具沙箱能直接执行，直连 API 引擎只有 4 个基础工具
        （含 read_file，按需读技能两套都成立）。"""
        eng = engines.get_engine()
        cap = bool((eng.capabilities() or {}).get("skills"))
        lib = config.AGENTS_DIR / config.SKILLS_REL
        lib_names = {p.name for p in lib.glob("*.md")} if lib.is_dir() else set()
        rows = [{"name": p.name, "desc": skills.describe(p / "SKILL.md"), "path": str(p),
                 "installed": (p.name + ".md") in lib_names}
                for p in skills.sources()
                if p.name and not p.name.startswith(".") and (p / "SKILL.md").exists()]
        return {"ok": True, "skills": rows, "engine": eng.name, "engineLabel": eng.label,
                "engineRunsSkills": cap,
                "msg": "" if rows else "本机没找到技能源（~/.dsh/skills、~/.agents/skills、npm 插件包三处）"}

    def _import_skill(self):
        body = self._body() or {}
        name = str(body.get("name", "")).strip()
        if not name:
            raise ApiError(400, "缺少技能名 name")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise ApiError(400, "技能名非法")
        src = next((p for p in skills.sources() if p.name == name), None)
        if src is None or not (src / "SKILL.md").is_file():
            raise ApiError(404, "本机技能源里没有「%s」" % name)
        lib = config.AGENTS_DIR / config.SKILLS_REL
        lib.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / "SKILL.md", lib / (name + ".md"))
        shutil.copytree(src, lib / name, dirs_exist_ok=True)
        return {"ok": True, "name": name, "installed": True,
                "msg": "已导入「" + name + "」到技能库", "skills": self._get_skill_sources()["skills"]}

    def _get_daily(self):
        return {"ok": True, "daily": knowledge.latest_daily()}

    def _get_events(self):
        since = int(self._qs().get("since", ["0"])[0] or 0)
        return runner.events(since)

    def do_GET(self):
        url = self.path.split("?", 1)[0]
        if url == "/":
            self._file(config.TEMPLATES / "index.html", "text/html; charset=utf-8")
        elif url.startswith("/static/"):
            rel = url[len("/static/"):]
            ctype = "text/css; charset=utf-8" if rel.endswith(".css") else "text/javascript; charset=utf-8"
            self._file(config.STATIC / rel, ctype)
        elif url == "/api/kb-entries":
            self._ok(lambda: {"ok": True, "manager": "老板助理R1",
                              "entries": knowledge.kb_entries()})
        elif url == "/api/md":
            self._ok(self._get_md, err=400)
        elif url == "/api/pending":
            self._ok(self._get_pending)
        elif url == "/api/summary":
            self._ok(self._get_summary)
        elif url == "/api/org":
            self._ok(lambda: {"ok": True, "roles": parsers.parse_roles()})
        elif url == "/api/timeline":
            self._ok(lambda: {"ok": True, **scheduler.get_timeline()})
        elif url == "/api/queue":
            self._ok(lambda: {"ok": True, "queue": self._queue_rows()})
        elif url == "/api/rn-outputs":
            self._ok(lambda: {"ok": True,
                              "groups": scheduler.rn_outputs(self._qs().get("no", [""])[0])})
        elif url == "/api/ws-files":
            self._ok(lambda: {"ok": True, "files": scheduler.ws_files()})
        elif url == "/api/project-files":
            self._ok(lambda: {"ok": True, **scheduler.project_files()})
        elif url == "/api/home-stats":
            self._ok(scheduler.home_stats)
        elif url == "/api/tokens":
            # 任务用量 + 临时会话用量分开给：前者按子任务逐条，后者是悬浮窗问答的合计
            self._ok(lambda: {"ok": True, "rows": scheduler.token_rows(),
                              "assistant": assistant.totals()})
        elif url == "/api/ws-file":
            self._ok(self._get_ws_file, err=400)
        elif url == "/api/ws-html":
            self._serve_html(self._qs())
        elif url == "/api/plan-rows":
            self._ok(lambda: {"ok": True, "rows": store.subtasks()})
        elif url == "/api/task-output":
            self._ok(self._get_task_output)
        elif url == "/api/sub-output":
            self._ok(self._get_sub_output)
        elif url == "/api/scheduler":
            self._json({"ok": True, "state": scheduler.SCHED_STATE})
        elif url == "/api/roles":
            self._json({"ok": True, "roles": [{"no": no, "name": name} for no, name in roles.role_files()]})
        elif url == "/api/roles/card":
            self._ok(self._get_role_card)
        elif url == "/api/skills":
            self._ok(self._get_skill_lib)
        elif url == "/api/skill-sources":
            self._ok(self._get_skill_sources)
        elif url == "/api/assistant/history":
            self._json({"ok": True, "items": assistant.records(limit=50),
                        "totals": assistant.totals()})
        elif url == "/api/templates":
            self._json({"ok": True, "templates": templates.templates()})
        elif url == "/api/handbook":
            self._json({"ok": True, "text": templates.handbook_text()})
        elif url == "/api/projects":
            self._json({"ok": True, "projects": config.projects(),
                        "active": config.active_project(), "seedRoles": config.settings_info()["seedRoles"]})
        elif url == "/api/settings":
            self._json(config.settings_info())
        elif url == "/api/engines":
            self._json({"ok": True, **engines.describe(),
                        "fallback": config.engine_fallback(config.ENGINE),
                        "configPath": str(config.CONFIG_FILE)})
        elif url == "/api/schedule":
            self._json({"ok": True, "schedules": config.schedule_status()})
        elif url == "/api/dirs":
            path = unquote(self._qs().get("path", [""])[0])
            self._json(config.list_dirs(path))
        elif url == "/api/run/events":
            self._ok(self._get_events)
        elif url == "/api/daily":
            self._ok(self._get_daily)
        else:
            self._json({"ok": False, "msg": "未知接口"}, 404)

    # ---------- 写端点 ----------
    def _post_retry(self):
        body = self._body()
        if body is None:
            raise ApiError(400, "JSON 解析失败")
        no = str(body.get("no", "")).strip()
        if not no:
            raise ApiError(400, "缺少任务编号 no")
        hit = [t for t in store.tasks() if t["no"] == no]
        if not hit:
            raise ApiError(404, "任务 " + no + " 不在队列中")
        st = scheduler.SCHED_STATE
        if st.get("busy") and no in (st.get("tag") or ""):
            raise ApiError(409, no + " 正在执行中，暂不可重试")
        retried = False
        if hit[0]["status"] in ("阻塞", "部分"):
            store.set_task(no, "待派")
            try:
                for s in store.subtasks(no):
                    if s["st"] != "完成":
                        store.set_subtask(s["no"], "待派")
            except Exception:
                pass
            retried = True
            scheduler.scan_once()  # 立即扫描：置待派后马上重启执行链（busy 时自然排队）
        return {"ok": True, "no": no, "retried": retried,
                "queue": self._queue_rows(),
                "msg": ("重试 " + no + "：已重置为待派并触发扫描（未完成子任务重新执行）") if retried
                       else (no + " 状态为「" + hit[0]["status"] + "」，无需重试")}

    def _post_dispatch(self):
        body = self._body()
        if body is None:
            raise ApiError(400, "JSON 解析失败")
        text = str(body.get("task", "")).strip()
        expect = str(body.get("expect", "R1 判断")).strip()
        if not text:
            raise ApiError(400, "任务内容不能为空")
        no = store.add_task(text, expect)
        scheduler.scan_once()  # 立即生成 R1 拆解指令，不等 8s 轮询
        return {"ok": True, "no": no, "queue": self._queue_rows(), "state": scheduler.SCHED_STATE}

    def _post_task_delete(self):
        body = self._body()
        if body is None:
            raise ApiError(400, "JSON 解析失败")
        no = str(body.get("no", "")).strip()
        if not no:
            raise ApiError(400, "缺少任务编号 no")
        if not any(t["no"] == no for t in store.tasks()):
            raise ApiError(404, "任务 " + no + " 不在队列中")
        # 停止子任务再删除：对执行中/待派/已派子任务先终止其运行中的 headless 子进程，
        # 并让执行链提前退出（不再执行剩余子任务、不重写产出），再删除任务，避免孤儿执行与产出残留。
        live = [s for s in store.subtasks(no) if s.get("st") in ("执行中", "待派", "已派")]
        if live:
            chain.mark_stopped(no)
            for s in live:
                runner.kill_spawn(s["no"])
        rep_n = len(store.reports(no))            # 删除将连带移除回报/批阅依据
        store.delete_task(no)
        removed = scheduler.clean_task_files(no)
        piyue_n = scheduler.clean_piyuetai(no)     # 批阅台里该任务的条目块一并清掉
        return {"ok": True, "no": no, "removedFiles": removed, "removedPiyue": piyue_n,
                "queue": self._queue_rows(),
                "msg": ("已删除任务 " + no + (" · 连带移除 " + str(rep_n) + " 条回报/批阅记录" if rep_n else "")
                        + ((" · 清理工作区文件 " + str(removed) + " 个") if removed else "")
                        + ((" · 清理批阅台条目 " + str(piyue_n) + " 条") if piyue_n else ""))}

    def _post_plan_pause(self):
        body = self._body() or {}
        act = str(body.get("action", "toggle"))
        if act == "toggle":
            scheduler.SCHED_STATE["paused"] = not scheduler.SCHED_STATE["paused"]
        elif act == "pause":
            scheduler.SCHED_STATE["paused"] = True
        else:
            scheduler.SCHED_STATE["paused"] = False
        p = scheduler.SCHED_STATE["paused"]
        return {"ok": True, "paused": p,
                "state": "已暂停：当前行跑完后停，剩余续跑（可点执行继续）" if p else "调度已恢复：可继续按派发单执行"}

    def _post_role_add(self, edit=False):
        body = self._body() or {}
        skills = _split_skills(body.get("skills"))     # None=未提交（edit 保留现卡清单）；[]=清空
        tags = _split_tags(body.get("tags"))           # None=未提交（edit 保留现卡标签）；[]=清空
        if edit:
            body_card = body.get("card")
            r = roles.edit_role(
                str(body.get("no", "")).strip(),
                name=str(body.get("name", "")).strip() or None,
                duty=str(body.get("duty", "")).strip() or None,
                position=str(body.get("position", "")).strip() or None,
                type_=str(body.get("type", "")).strip() or None,
                skills=skills,
                tags=tags,
                card=(str(body_card).strip() if isinstance(body_card, str) and str(body_card).strip() else None),
                dry=bool(body.get("dry", False)))
        else:
            r = roles.add_role(
                str(body.get("name", "")).strip() or "新角色",
                str(body.get("duty", "")).strip() or "待补充职责",
                str(body.get("position", "")).strip() or "一句话定位",
                str(body.get("type", "")).strip() or "业务",
                skills=skills or (),
                tags=tags or (),
                dry=bool(body.get("dry", False)))
        return {"ok": True, **({"preview": True} if body.get("dry") else {}), "result": r}

    def _post_project(self):
        # 一个端点三种动作：add / switch / remove（项目以 root 路径为唯一键）
        body = self._body() or {}
        act = str(body.get("action") or "").strip()
        root = str(body.get("root") or "").strip()
        if act in ("switch", "remove") and scheduler.SCHED_STATE.get("busy"):
            # 切换会把 ROOT/台账/角色目录整体换掉，执行链跑一半时切会写串项目
            raise ApiError(409, "当前有任务正在执行，等执行链跑完再切换项目")
        if act == "add":
            p = config.add_project(str(body.get("name") or ""), root,
                                   template=str(body.get("template") or "large_dev"))
            bootstrap.bootstrap()          # 建三目录 + 从 agents-seed 复制角色卡
            return {"ok": True, "project": p, "boot": bootstrap.BOOT_LOG, **config.settings_info()}
        if act == "switch":
            p = config.switch_project(root)
            bootstrap.bootstrap()
            return {"ok": True, "project": p, "boot": bootstrap.BOOT_LOG, **config.settings_info()}
        if act == "remove":
            res = config.remove_project(root)
            return {"ok": True, "result": res, **config.settings_info()}
        raise ApiError(400, "未知动作：" + act)

    def _post_settings(self):
        # 一个端点服务两种保存：模型接入（body.model）与 根目录/端口（SETTING_KEYS）。
        # 原来写成两个同名分支，第二个永远走不到 —— 保存根目录会落进只处理 model 的
        # 那个分支：根目录从未写盘（界面却显示成功），还顺手把 model 段重置成默认 provider。
        try:
            body = self._body() or {}
            dry = bool(body.get("dry", False))
            kv = {k: body.get(k) for k in config.SETTING_KEYS if k in body}
            if kv.get("port") not in (None, ""):
                try:
                    kv["port"] = int(str(kv["port"]).strip())
                except Exception:
                    kv.pop("port", None)
            eng = str(kv.get("engine") or "").strip().lower()
            if eng:                                  # 引擎名必须是已注册的，写错当场报错而不是留到派发
                if eng not in engines.available():
                    raise ApiError(400, "未知执行引擎：%s（可用：%s）"
                                   % (eng, "、".join(engines.available()) or "无"))
                kv["engine"] = eng
            fb = kv.get("engineFallback")
            if fb is not None:                       # 备用引擎（主引擎失败时兜底），空 = 关闭
                fb = str(fb).strip().lower()
                if fb and fb not in engines.available():
                    raise ApiError(400, "未知备用引擎：%s（可用：%s）"
                                   % (fb, "、".join(engines.available()) or "无"))
                kv["engineFallback"] = fb
            out = {"ok": True}
            if kv and not dry:
                config.save_cfg(kv)
                config.reload()
                bootstrap.bootstrap()      # 新根目录下的三目录幂等重建
                out.update(config.settings_info())
                out["engines"] = engines.describe()      # 切换后立即回带新状态，前端不用再拉一次
                out["engines"]["fallback"] = config.engine_fallback(config.ENGINE)
                out["boot"] = bootstrap.BOOT_LOG
            mbody = body.get("model")
            if isinstance(mbody, dict):
                res = config.save_model(mbody, dry=dry)
                mi = config.model_info()
                res["configured"] = mi["configured"]
                res["keyMasked"] = mi["keyMasked"]
                out["model"] = res         # 放在 settings_info 之后，否则被其 model 字段盖掉
            out["msg"] = "；".join(x for x in (
                "模型 API 配置已保存" if isinstance(mbody, dict) else "",
                ("执行引擎已切换到 " + eng) if eng else "",
                "opc-config.json 已更新并生效" if kv else "",
                "端口修改需重启控制台" if "port" in kv else "",
            ) if x) or "无改动"
            return out
        except ApiError:
            raise                    # 校验类错误原样抛出（400），别包成「保存设置失败」
        except Exception as e:
            raise ApiError(500, "保存设置失败: " + str(e)[:200])

    def _post_assistant_ask(self):
        """R1 助理的临时会话：只问答，不建任务、不派角色（用量单独记账）。"""
        body = self._body() or {}
        return assistant.ask(str(body.get("q") or ""))

    def _post_model_test(self):
        try:
            return config.test_model(self._body() or {}, timeout=20)
        except Exception as e:
            raise ApiError(500, "模型连通测试异常: " + str(e)[:200])

    def _post_schedule(self):
        body = self._body() or {}
        action = str(body.get("action") or "add")
        jobs = config.load_schedules()
        if action == "add":
            jobs.append({
                "id": "sched-%d" % (len(jobs) + 1),
                "task": str(body.get("task") or "").strip(),
                "mode": str(body.get("mode") or "daily").strip(),
                "time": str(body.get("time") or "").strip(),
                "weekday": str(body.get("weekday") or "").strip(),
                "intervalMin": str(body.get("intervalMin") or "").strip(),
                "enabled": True,
            })
        elif action == "toggle":
            sid = str(body.get("id") or "")
            for j in jobs:
                if j.get("id") == sid:
                    j["enabled"] = not j.get("enabled", True)
        elif action == "update":
            sid = str(body.get("id") or "")
            for j in jobs:
                if j.get("id") == sid:
                    for k in ("task", "mode", "time", "weekday", "intervalMin"):
                        if body.get(k) is not None:
                            j[k] = str(body.get(k)).strip()
                    if body.get("enabled") is not None:
                        j["enabled"] = bool(body.get("enabled"))
        elif action == "delete":
            sid = str(body.get("id") or "")
            jobs = [j for j in jobs if j.get("id") != sid]
        else:
            raise ApiError(400, "未知动作：" + action)
        config.save_schedules(jobs)
        return {"ok": True, "schedules": config.schedule_status(jobs)}

    def _post_work_archive(self):
        body = self._body() or {}
        item = int(str(body.get("item", "0")).strip() or 0)
        if item <= 0:
            raise ApiError(400, "缺少工作条目编号")
        title = review.archive_work(item)
        return {"ok": True, "item": item, "title": title,
                "msg": "工作 #%d「%s」已归档（标记已阅）" % (item, (title or "")[:40])}

    def _post_piyue(self):
        body = self._body()
        if body is None:
            raise ApiError(400, "JSON 解析失败")
        item = str(body.get("item", "")).strip()
        judge = str(body.get("judge", ""))
        opinion = str(body.get("opinion", "")).strip()
        if not item:
            raise ApiError(400, "缺少待决编号")
        new_line = review.write_piyue(item, judge, opinion)
        # R0 批阅后，R1 一律重新派发执行：批准→执行决策；驳回/修改→按批注修改后重报，直到批准。
        extra = {}
        try:
            verb = review.verb_of(judge)
            # R1 自己判断：是否需要派发任务给员工执行（模型判断，判不了回退规则）
            resp = scheduler._r1_respond(item, judge, opinion)
            if resp is None:
                # 模型未给出判断：回退规则（驳回不派；批准/修改派）
                if verb == "驳回":
                    review.append_r1_exec(item, "已驳回，不再派发执行")
                    extra = {"task": None}
                elif verb == "批准":
                    task_text = "执行 R0 决策（批阅台 待决 #%s）：%s" % (item, opinion or "按批阅意见执行")
                    no = store.add_task(task_text, "R1 判断")
                    review.append_r1_exec(item, "已建任务 %s，待 R1 派发执行" % no)
                    scheduler.scan_once()
                    extra = {"task": no}
                else:  # 修改：按批注修改后重报
                    task_text = "按批阅修改（批阅台 待决 #%s，修改）：%s" % (item, opinion or "按批注修改后重报")
                    no = store.add_task(task_text, "R1 判断")
                    review.append_r1_exec(item, "已按批注重新派发执行 %s" % no)
                    scheduler.scan_once()
                    extra = {"task": no}
            elif resp.get("dispatch"):
                tt = str(resp.get("task") or "").strip() or ("执行 R0 决策（批阅台 待决 #%s）" % item)
                try:
                    no = store.add_task(tt, "R1 判断")
                    review.append_r1_exec(item, "已按 R0 裁决派发任务 %s" % no)
                    scheduler.scan_once()
                    extra = {"task": no}
                except Exception:
                    extra = {"task": None}
            else:
                review.append_r1_exec(item, "已按 R0 裁决处理，未触发新派发")
                extra = {"task": None}
        except Exception:
            extra = {"task": None}
        return {"ok": True, "line": new_line, "item": item, **extra}

    def do_POST(self):
        url = self.path.split("?", 1)[0]
        if url == "/api/retry":
            self._ok(self._post_retry)
        elif url == "/api/dispatch":
            self._ok(self._post_dispatch)
        elif url == "/api/task-delete":
            self._ok(self._post_task_delete)
        elif url == "/api/plan-execute":
            self._ok(lambda: {"ok": True, "result": scheduler.plan_execute()})
        elif url == "/api/plan-pause":
            self._ok(self._post_plan_pause)
        elif url == "/api/roles/add":
            self._ok(self._post_role_add)
        elif url == "/api/roles/edit":
            self._ok(lambda: self._post_role_add(edit=True))
        elif url == "/api/projects":
            self._ok(self._post_project, err=400)
        elif url == "/api/settings":
            self._ok(self._post_settings)
        elif url == "/api/assistant/ask":
            self._ok(self._post_assistant_ask)
        elif url == "/api/model/test":
            self._ok(self._post_model_test)
        elif url == "/api/roles/delete":
            def h():
                body = self._body() or {}
                try:
                    return {"ok": True, "result": roles.remove_role(str(body.get("no", "")).strip())}
                except ValueError as e:
                    raise ApiError(409, str(e))
            self._ok(h)
        elif url == "/api/timeline":
            self._ok(lambda: scheduler.build_timeline())
        elif url == "/api/schedule":
            self._ok(self._post_schedule)
        elif url == "/api/work-archive":
            self._ok(self._post_work_archive, err=400)
        elif url == "/api/piyue":
            self._ok(self._post_piyue, err=400)
        elif url == "/api/skill-import":
            self._ok(self._import_skill, err=400)
        else:
            self._json({"ok": False, "msg": "未知接口"}, 404)


def create_server():
    return ThreadingHTTPServer((config.HOST, config.PORT), Handler)
