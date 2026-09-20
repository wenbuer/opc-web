# OPC 智能体工作台

[English](README.en.md) · 简体中文

[![tests](https://github.com/wenbuer/opc-web/actions/workflows/test.yml/badge.svg)](https://github.com/wenbuer/opc-web/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![runtime](https://img.shields.io/badge/runtime-stdlib%20%2B%20zstandard-brightgreen.svg)](pyproject.toml)
[![engine](https://img.shields.io/badge/engine-API%20%7C%20DSH-blueviolet.svg)](#执行引擎)
[![network](https://img.shields.io/badge/network-127.0.0.1%20only-purple.svg)](#配置与数据)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 简介

opc-web 是一个本地运行的「AI 员工团队」管理控制台。它把一条任务从下达到归档的全过程收在同一个界面里：下达需求、查看拆解与执行、审阅产出、作出裁决、沉淀档案。

角色分三级：

- **R0**：人。定方向、承担实际支出、作出裁决。
- **R1**：助理。拆解任务，按优先级与峰谷决定派发时机，汇总回报，提炼需要人裁决的决策点，归档。
- **RX**：执行角色。带角色卡与装配好的技能，在项目工作区里使用工具完成子任务，并写出回报。

执行角色由可替换的执行引擎驱动：默认直连大模型 API，也可以换成 DSH（DeepSeek Harness）headless。

运行要求与边界：

- Python 3.9+；除 `zstandard`（用于读取 DSH 会话日志的用量与心跳）外只用标准库。
- 任务状态写本地 SQLite，产出与知识档案写 Markdown；控制台只监听 `127.0.0.1`。
- 运行数据全部落在本机项目目录，不向外部服务发送。

## 预览

<table>
<tr>
<td width="25%"><img src="images/opc-command-center-01.png" alt="作战面板"><br><sub>作战面板 · 概览</sub></td>
<td width="25%"><img src="images/opc-command-center-02.png" alt="批阅台"><br><sub>批阅台 · 决策建议与裁决</sub></td>
<td width="25%"><img src="images/opc-command-center-03.png" alt="工作台"><br><sub>工作台 · 下达任务、四列看板与实时事件</sub></td>
<td width="25%"><img src="images/opc-command-center-04.png" alt="运行日志全屏"><br><sub>运行日志 · 自动执行链完整轨迹</sub></td>
</tr>
<tr>
<td width="25%"><img src="images/opc-command-center-05.png" alt="项目文件"><br><sub>项目文件 · 工程产出区</sub></td>
<td width="25%"><img src="images/opc-command-center-06.png" alt="知识库"><br><sub>知识库 · 按主题分类的档案卡片</sub></td>
<td width="25%"><img src="images/opc-command-center-07.png" alt="每日简报"><br><sub>每日简报 · 当天摘要</sub></td>
<td width="25%"><img src="images/opc-command-center-08.png" alt="设置 Token 统计"><br><sub>设置 · Token 用量</sub></td>
</tr>
</table>

<p align="center">
  <img src="images/opc-task-loop-01.png" alt="任务闭环：任务 → 角色 → 解释，转回任务" width="880">
  <br>
  <em>任务闭环：人在 ① 下达与 ⑧ 批阅出场（红）；②③⑥⑦ 由 R1 承担（蓝）；④⑤ 由 RX 角色执行（紫）。</em>
</p>

## 目录

- [简介](#简介)
- [预览](#预览)
- [工作流程](#工作流程)
- [功能](#功能)
- [快速开始](#快速开始)
- [界面导览](#界面导览)
- [执行引擎](#执行引擎)
- [配置与数据](#配置与数据)
- [目录结构](#目录结构)
- [开发与测试](#开发与测试)
- [贡献](#贡献)
- [许可证](#许可证)

## 工作流程

一条任务从下达到收口走八步一圈：

```text
① 下达（R0）→ ② 拆解（R1）→ ③ 排队派发（R1）→ ④ 执行（RX）
                                                              ↓
⑧ 批阅与沉淀（R0/R1）← ⑦ 呈报（R1）← ⑥ 归档（R1）← ⑤ 回报（RX）
```

| 阶段 | 承担者 | 做什么 |
|---|---|---|
| 任务 | R0 · R1 | 人说清要什么；R1 拆成能独立交付的子任务，并按优先级与峰谷决定何时开跑 |
| 角色 | RX | 带角色卡与技能在项目内使用工具干活，产出落工作区并写回报 |
| 解释 | R1 · R0 | R1 把回报汇总成人能读懂的内容，需要裁决的给出决策建议；R0 批阅，批注即新指令 |

一轮跑完，产出同时进台账与知识库；上一轮的结论作为下一轮的输入。

## 功能

### 任务与派发

- **自动拆解**：按「能否独立交付」把一句话拆成 1~3 个子任务，每项点名角色并写明期望产出；也可指定角色直派，跳过拆解。
- **队列优先级**：子任务看板「待派」每条带一个单字芯片（高 / 普 / 低），点击循环切换。调度挑选任务与任务内执行顺序都依据它。
- **峰谷调度**：官方峰时为工作日 09:00-12:00 与 14:00-18:00（三档单价翻倍）。拆出 2 项及以上的长任务在峰时排队，到谷时自动开跑；单点子任务不受影响。任务行上的「立即执行」可豁免峰时并插到队首。
- **定时任务**：支持每天 / 每周 / 每隔 N 分钟。任务存在项目数据目录（`批阅台/定时任务.json`），随项目走。

### 执行引擎与护栏

- **可替换引擎**：默认直连大模型 API，也可切换为 DSH（DeepSeek Harness）headless；两套引擎共用同一套进度与用量口径，主引擎不可用时回退到备用引擎。详见[执行引擎](#执行引擎)。
- **技能装配**：R0 / R1 / RX 三级岗位，界面增删角色自动编号；技能存放在共享技能库，角色卡登记即装配，也可从本机技能源导入。技能与引擎无关。
- **过程可见**：角色卡显示当前任务代号；工作台四列看板（待派 / 已派 / 完成 / 阻塞）配实时事件流，可看到执行到哪一步、调用了什么工具。
- **执行护栏**：单次运行设三道上限 —— 轮数 300、工具调用 320、累计输入 3000 万 token，任一越界立即中止。被中止的运行按**阻塞**收口并留痕：产出文件可能已有部分内容，但不会记为完成。
- **异常留痕**：归档、元数据与收尾链路的异常一律记入事件流，不静默丢弃。

### 回报、批阅与知识

- **回报落盘**：产出写 `工作区/<角色>/T-xxx-Sn-report.md` 与同名 `.meta.json`（记引擎、会话、用量）；完成后正文移入 `已归档/`，回报进台账。文件位置即处理状态：在工作区为待处理，移入 `已归档/` 为已处理。
- **批阅驱动执行**：批准会立即创建「执行 R0 决策」任务继续推进；驳回则按批注重做，形成「下达 → 执行 → 批阅 → 归档」的闭环。批阅台分三段各自滚动：工作内容 / 决策裁决 / 已批阅归档。
- **决策点分离**：每个任务都进「工作内容」；只有确实需要裁决的（方向取舍、对外支出、例外授权、验收定稿）才另加一条「待决 N」，两条同号。归档口径、是否结案这类流程事项由控制台处理，不占用决策位。
- **知识库**：任务收尾时由 R1 判断是否值得沉淀，有价值才按主题域归档，同主题合并进已有档案；每篇带 OKF front-matter（知识型 / 建档 / 更新 / 来源任务）。
- **每日简报**：当天任务自动汇总。写入前做结构校验，模型返回的包装（前置说明、代码块围栏、结尾注）会被剥除；校验不通过则不落盘，改走代码级合并。

### 成本与调度

- **三档计价**：新输入 / 缓存命中 / 输出分别计量与计价。台账里的 `tokensIn` 是「新输入 + 缓存读取」的合计，而缓存命中价通常远低于输入价，因此出账时先减缓存再按输入价计。首页自动换算单位并同时给出总额与今日。
- **运行开关**：R1 助理悬浮窗、峰时长任务排队等开关集中在「设置 → 运行开关」，写入项目配置持久化。

### 运行与部署

- **本地优先**：SQLite 与 Markdown，仅监听本机，数据可回溯。
- **依赖极少**：除 `zstandard` 外均为标准库；启动入口 `run.py`，Windows 可双击 `启动控制台.bat`，macOS / Linux 可用 `run.sh`。
- **主题**：深浅双主题，一键切换并记忆。

## 快速开始

**环境要求**：Python 3.9+（Windows / macOS / Linux 均在 CI 中验证）。可选依赖 `zstandard`：仅在使用 DSH 引擎读取会话日志时需要，只跑直连 API 引擎可以不装。

```bash
git clone https://github.com/wenbuer/opc-web.git
cd opc-web
pip install zstandard        # 可选
python run.py                # → http://127.0.0.1:8901（启动后自动打开浏览器）
```

Windows 也可双击 `启动控制台.bat`，macOS / Linux 用 `sh run.sh`（两者都只是 `python run.py` 的封装）。

**Docker**（数据落在 `opc-data` 卷；容器内需显式指定监听地址）：

```bash
docker build -t opc-web .
docker run --rm -p 8901:8901 -v opc-data:/data -e DEEPSEEK_API_KEY=sk-... opc-web
```

首次启动三步：

1. 打开 http://127.0.0.1:8901（首次启动自动生成目录与骨架文件）；
2. 在「设置 → 模型接入」填入大模型 API Key，并填写三档单价（也可复制 `.env.example` 为 `.env` 手动填写）；
3. 在「作战面板」或「工作台」下达第一个任务。

> 目前未发布到 PyPI。随包资源（`templates/`、`static/`、`agents-seed/`）尚未整理进 wheel，请使用上面的 clone 方式安装。

## 界面导览

| 视图 | 作用 |
|---|---|
| **作战面板** | 组织架构、角色卡状态与项目时间线；顶部概览：任务状态（待办 / 进行中 / 已完成）、Token 消耗（含今日）、项目成本（含今日）、知识库文件数、最近简报 |
| **工作台** | 下达任务、四列子任务看板（待派列带优先级芯片与「立即执行」）、任务详情、实时事件流 |
| **批阅台** | 对回报批准 / 驳回 / 修改，裁决直接驱动后续派发；三段独立滚动：工作内容 / 决策裁决 / 已批阅归档 |
| **项目文件** | 按角色 / 项目 / 任务筛选产物，默认落在「项目/」工程产出区；支持 Markdown 渲染、HTML 内嵌预览与全屏 |
| **知识库** | 按分类阅读档案，卡片标出知识型与建档 / 更新 / 来源任务 |
| **每日简报** | 查看当天任务汇总生成的简报 |
| **设置** | 项目选择、执行引擎、模型接入（含三档单价与峰谷提示）、定时任务、Token 统计、Skill 导入、运行开关 |

## 执行引擎

执行角色任务的引擎可替换，在 `opc-config.json` 中配置：

| 引擎 | 说明 |
|---|---|
| `api`（默认） | 直连大模型 API 的 agent 循环：内置 4 个工具（列目录 / 读文件 / 写文件 / 跑命令），流式进度与用量取自 API 返回；沿用「设置 → 模型接入」的提供方与密钥 |
| `dsh` | 调用 `dsh --profile headless` 执行；自带工具沙箱与技能生态，用量与进度从会话日志读取 |

```jsonc
{
  "engine": "dsh",                  // 主引擎（api | dsh）
  "engineFallback": "api",          // 主引擎未跑起来时改用它
  "engineFor": {                    // 按用途路由，留空即用主引擎
    "prompt": "api",                //   拆解 / 汇总这类轻文本推理
    "execute": "dsh"                //   角色任务执行
  },
  "model": { "provider": "deepseek" }   // 模型接入：api 引擎沿用这份配置
}
```

修改后刷新页面即生效，无需重启。设置页的「执行引擎」只显示当前引擎与可用性（含配置文件路径），不提供切换按钮，引擎选择统一走配置文件。

补充说明：

- 引擎名写错会直接报错，不会静默退回；
- **按用途路由**：`engineFor` 可为 `prompt`（拆解 / 汇总）与 `execute`（角色任务）分别指定引擎；
- **技能与引擎无关**：技能导入后进入共享技能库，由角色卡登记装配，执行时拼进角色 prompt；两套引擎使用同一份技能，差别只在能否直接执行技能中的命令与读写步骤；
- **能力如实声明**：引擎自报是否支持步数上限等能力（DSH headless 无步数开关，即标记为不支持，改由执行护栏兜底），界面与调用方据此降级；
- **失败回退**：主引擎报错或秒退无产出时，自动改用备用引擎重跑一次；长时间运行但无产出的视为任务问题，不重跑，取消也不回退，回退会留痕（工作台可见）。

> 环境变量 `OPC_ENGINE` / `OPC_ENGINE_FALLBACK` 优先于配置文件，界面会提示这一点。

## 配置与数据

优先级：**环境变量 > `opc-config.json` > 默认值**（配置文件不入库）。

| 字段 | 默认 | 说明 |
|---|---|---|
| `root` | 项目根 | 总根目录，其下自动生成 批阅台 / 工作区 / 知识库 |
| `port` | `8901` | 监听端口（修改后需重启） |
| `engine` | `api` | 执行引擎名（见上节） |
| `engineFallback` | `api` | 主引擎失败时的备用引擎；与主引擎相同即不启用 |
| `engineFor` | `{}` | 按用途路由：`{prompt, execute}`，留空即用主引擎 |
| `model` | — | `{provider, apiKeyEnv?, baseURL?, model?}`；密钥不写在此处 |
| `priceIn` / `priceCache` / `priceOut` | `1 / 1 / 2` | 三档单价（元 / 百万 token）；`priceCache` 留空即按输入价计算，在「设置 → 模型接入」填写 |
| `peakDefer` | `true` | 峰时是否自动延后长任务 |
| `assistantDock` | `true` | R1 助理悬浮窗 |
| `schedule` | `[]` | 定时任务（实际存储在项目数据目录，见下表） |
| `pollSeconds` | `8` | 调度守护轮询间隔（秒） |
| `decomposeTimeout` | `480` | 拆解任务时 headless 的无输出超时（秒） |
| `maxSubtasks` | `3` | 单任务最多拆成几个子任务 |
| `fallbackMaxElapsed` | `60` | 判定「秒退无产出」的秒数，超过则不回退重跑 |

**环境变量**：`OPC_CONFIG`（配置文件路径）、`OPC_KB_ROOT`（项目数据根）、`OPC_HOST`（监听地址，默认 `127.0.0.1`，仅容器等场景改为 `0.0.0.0`）、`OPC_PORT`（端口）、`OPC_ENGINE`（引擎）、`OPC_ENGINE_FALLBACK`（备用引擎）、`OPC_TOKEN_PRICE_IN` / `_CACHE` / `_OUT`（三档单价）。

| 数据 | 位置 |
|---|---|
| API 凭据 | 项目根 `.env`（不进配置、不回显、不入库） |
| 台账 | `批阅台/opc.db`（SQLite）：任务 / 子任务 / 回报 / 执行记录 |
| 定时任务 | `批阅台/定时任务.json`（随项目走） |
| 产物 | `工作区/<角色名>/T-xxx-Sn-report.md` + 同名 `.meta.json`，完成后移入 `已归档/` |
| 运行日志 | `批阅台/运行日志/T-xxx-Sn.log`（完整轨迹） |
| 知识档案 | `知识库/<分类>/<标题>.md`，带 OKF front-matter（`type` / `created` / `updated` / `task`） |
| 运行数据 | 批阅台 / 工作区 / 知识库在启动时幂等生成，不入库 |

## 目录结构

```text
run.py              启动入口
src/opc_web/        控制台源码：config / server / scheduler / chain / store /
                    agent / roles / review / engines（api 与 dsh 两套实现）/ skills
templates/          页面
static/             样式与脚本
agents-seed/        新建项目时的角色卡种子
skills/             项目内技能（随代码走，不进全局技能目录）
tests/              用例（18 个文件，每个都能单独运行）
scripts/            run_tests.py（运行全部用例）
                    build.ps1 + opc-web.spec（PyInstaller 打包）
.github/            CI（Windows + Linux × Python 3.9/3.13）与 issue / PR 模板
images/             README 配图
CHANGELOG.md        更新日志
Dockerfile          容器构建（配 .dockerignore）
run.sh              macOS / Linux 启动入口
启动控制台.bat       Windows 启动入口
```

## 开发与测试

- **前端改动**：修改 `static/*.css`、`static/*.js` 或 `templates/index.html` 无需重启服务，递增引用中的 `?v=` 参数后强制刷新即可；修改 `src/opc_web/*.py` 才需要重启。
- **运行用例**：

```bash
pip install zstandard        # 其中两个套件（dsh 用量 / 执行心跳）需要它
python scripts/run_tests.py  # 逐个运行 18 个用例文件；也可单独运行 python tests/test_core.py
```

- **CI**：`.github/workflows/test.yml`，Windows + Linux × Python 3.9 / 3.13 共四组，主干 push 与 PR 触发。失败时会输出 `::error` 注解与 job summary，无需登录即可在 commit 的 checks 里看到失败用例与输出片段。
- **打包**：`scripts/build.ps1` + `scripts/opc-web.spec`（PyInstaller onedir，Windows）。

## 贡献

提交 PR 前请确认：

1. `python scripts/run_tests.py` 全部通过；若改动了行为，请补一个用例 —— `tests/` 中的用例都是单文件、单进程、不依赖测试框架的写法，可参照现有文件编写；
2. 提交信息写清改前、改后与原因；版本变更另见 [CHANGELOG.md](CHANGELOG.md)；
3. 界面改动附改动前后的对比图（图片放在 `images/`，README 中以相对路径引用）。

问题与建议请提交 [issue](https://github.com/wenbuer/opc-web/issues)（含 bug 报告与功能建议两个模板）。

## 许可证

[MIT License](LICENSE)
