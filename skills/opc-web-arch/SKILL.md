---
name: opc-web-arch
description: OPC 控制台的架构地图：三个仓库边界、路径常量、执行链、落盘位置。改 opc-web 之前加载，省掉重新摸代码的一轮。
---

# 架构地图

## 三个仓库（各自独立快照）

| 仓库 | 内容 | 远程 |
|---|---|---|
| `OPC-APP/`（根） | `keeptalk/`、`opc-data/`、根文件 | 有 |
| `opc-web/` | 控制台本体 | `git@github.com:wenbuer/opc-web.git` |
| `keeptalk/` | 项目数据（工作区/批阅台/知识库/agents） | 无 |

## 路径常量（config.py）

- `BASE` = 程序所在目录（打包后是 exe 目录）。**`.env` 与 `opc-config.json` 硬编码在 BASE 下，不能挪**
- `ASSET` = `BASE/_internal`（打包 onedir 时存在）否则 `BASE` —— `templates/ static/ _seed/` 从这里找
- `ROOT` = 项目根（`keeptalk/`）；`WORKSPACE_ROOT` / `BATCH_ROOT` / `KB_ROOT` / `PROJECT_ROOT` 随之派生

## 执行链

```
下达任务 → store.add_task → chain.execute
  → decompose（R1 拆解，purpose=prompt）
  → 逐子任务：prepare_files（预置产出与 meta 骨架）→ 引擎执行（purpose=execute）
  → 回报落库 → r1_archive（正文移入 已归档/、meta 同步）
```

- **引擎**：`dsh`（默认，headless，带工具沙箱）/ `api`（直连，4 个基础工具）；`config.engine_for(purpose)` 路由，失败自动回退
- **直派**（跳过拆解）：`chain.execute(no, text, direct={"role","sub","expect"})` —— 角色卡片上的终端入口走它

## 落盘位置

| 路径 | 内容 |
|---|---|
| `批阅台/opc.db` | 台账（任务 / 子任务 / 回报 / 执行记录） |
| `批阅台/运行日志/T-xxx-Sn.log` | 完整执行轨迹（思考 / 工具 / 输出） |
| `批阅台/临时会话.jsonl` | R1 助理问答用量 |
| `工作区/<角色>/T-xxx-Sn-*.md` | 角色产出（工作中 `-report` → 归档 `-output`） |
| `logs/` | 控制台自身 stdout/stderr（gitignore） |

## 铁律（都是踩过的坑）

1. **角色 agent 会抢先写 meta 的 status** —— 它按 prompt 要求把 status 改成「完成」，归档线程看到就搬走文件，执行链回来更新 meta 时文件已不在原地（`FileNotFoundError` 被 `except: pass` 吞掉）。
   归档守卫的判据必须是 **`runner.exec_state()`（当前进程真的在跑）**，**不能用 DB 的未结算记录** —— 进程被杀会留下永久为真的假信号，把子任务永久卡在「执行中」。
2. **dsh 用量要逐轮累加**：`assistant/message` 的 usage 是**单轮值**不是累计值；只取最后一条会漏掉前面所有轮次（实测 174k 输入记成 26k，少记 85%），与逐轮累加的 api 引擎没法比。
3. **两个引擎的记账口径必须一致**，否则「哪个引擎更省」是个假问题。
4. **`tokensIn` 已含 cacheRead**；`tokensCacheRead` 单列，供界面拆「缓存命中 / 新输入」。
5. **DSH 0.1.5 起会话日志叫 `session.v3.jsonl.zstd`**（旧名 `session.jsonl.zstd` 不再写）；只认旧名会读到上次运行留下的陈旧文件 → 心跳不刷新、用量读不到。
