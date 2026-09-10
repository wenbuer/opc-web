# OPC 智能体工作台（opc-web）

> 用一支能长期协作的 **AI 员工团队**把活干完：配置岗位、装配技能、下达任务，拆解 / 执行 / 汇总 / 归档由团队自主完成——你只负责审阅与拍板。

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![python deps](https://img.shields.io/badge/python%20deps-0%20pip%20packages-brightgreen.svg)](pyproject.toml)
[![runtime](https://img.shields.io/badge/runtime-requires%20DSH-important.svg)](#快速开始)
[![network](https://img.shields.io/badge/network-127.0.0.1%20only-purple.svg)](#配置与数据)
[![stars](https://img.shields.io/github/stars/wenbuer/opc-web-dsh?style=social)](https://github.com/wenbuer/opc-web-dsh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 简介

opc-web 是一个本地运行的「AI 员工团队」管理控制台。你创建岗位、给岗位装技能，然后下达需求、审阅结果、作出决策；团队负责拆解、执行、汇总与归档。

- **控制台（本项目）**：Python 3.9+ 标准库实现，**零第三方依赖**，仅监听本机 `127.0.0.1`
- **执行角色**：由**可替换的执行引擎**驱动——默认 DSH（DeepSeek Harness）headless，也可直连大模型 API 自建 agent 循环（见[执行引擎](#执行引擎)）

> **R0** 下达与拍板 → **R1** 拆解与归档 → **RX** 执行与回报。状态存本地 SQLite、正文走 md，**不上云、不外传**。

---

## 预览

<table>
<tr>
<td width="25%"><img src="images/opc-command-center-01.png" alt="作战面板"><br><sub>作战面板 · 组织架构与角色状态</sub></td>
<td width="25%"><img src="images/opc-command-center-02.png" alt="工作台"><br><sub>工作台 · 下达任务与看板</sub></td>
<td width="25%"><img src="images/opc-command-center-03.png" alt="批阅台"><br><sub>批阅台 · 裁决角色回报</sub></td>
<td width="25%"><img src="images/opc-command-center-04.png" alt="项目文件"><br><sub>项目文件 · 工作区产物</sub></td>
</tr>
<tr>
<td width="25%"><img src="images/opc-command-center-05.png" alt="知识库（浅色）"><br><sub>知识库 · 浅色主题</sub></td>
<td width="25%"><img src="images/opc-command-center-06.png" alt="知识库（深色）"><br><sub>知识库 · 深色主题</sub></td>
<td width="25%"><img src="images/opc-command-center-07.png" alt="每日简报"><br><sub>每日简报 · 当天摘要</sub></td>
<td width="25%"><img src="images/opc-command-center-08.png" alt="设置 Token 统计"><br><sub>设置 · Token 用量</sub></td>
</tr>
</table>

---

## 特性

- **岗位体系与技能装配**：R0 / R1 / RX 三级岗位，界面增删角色自动编号；技能放在共享技能库、角色卡登记即装配，也可从 dsh 一键导入。
- **自动拆解与派发**：下达一句话，自动拆成子任务并派给对应角色执行；支持点名直派，拆解数量宁少勿多并设上限。
- **批阅即驱动执行**：批准会立即创建「执行 R0 决策」任务继续往下跑，驳回则按批注重做——形成「下达 → 执行 → 批阅 → 归档」闭环。
- **过程实时可见**：角色卡显示当前任务代号；工作台四列看板（待派 / 已派 / 完成 / 阻塞）配实时事件流，能看到执行到哪一步、调了什么工具。
- **可替换执行引擎**：dsh 与「直连 API 自建 agent 循环」两套实现，改配置即切换，上层调用零改动。
- **本地零依赖**：Python 标准库 + SQLite + md 文件，仅监听本机；数据全在本地，可回溯、不上云。
- **深浅双主题**：一键切换并记忆。

---

## 快速开始

**环境要求**：Python 3.9+；默认执行引擎需要 **DSH**（DeepSeek Harness）。

```bash
python run.py                 # 命令行启动（推荐）
# Windows 也可双击「启动控制台.bat」（自动开浏览器）
```

1. 访问 http://127.0.0.1:8901（首次启动自动生成目录与骨架文件）；
2. 到「设置 → 模型接入」填入大模型 API Key；
3. 在「作战面板」或「工作台」下达第一个任务。

---

## 界面导览

| 视图 | 作用 |
|---|---|
| **作战面板** | 组织架构、角色卡状态与当前任务；顶部概览统计待办 / 进行中 / 已完成 / Token / 知识 / 简报 |
| **工作台** | 下达任务、四列子任务看板、任务详情、实时事件流 |
| **批阅台** | R0 对回报批准 / 驳回 / 修改；裁决直接驱动后续派发 |
| **项目文件** | 按角色 / 项目 / 任务筛选产物；md 渲染、HTML 内嵌预览并可全屏 |
| **知识库** | 按分类分组阅读档案，组头可展开收起 |
| **每日简报** | R1 汇总当天任务生成的摘要简报 |
| **设置** | 项目目录与端口、模型接入、定时任务、Token 统计、Skill 导入 |

---

## 执行引擎

执行角色任务的「引擎」可替换（`opc-config.json` 的 `engine`，或环境变量 `OPC_ENGINE`）：

| 引擎 | 说明 |
|---|---|
| `dsh`（默认） | 调用 `dsh --profile headless` 执行；自带工具沙箱与技能生态，用量与进度从会话日志读取 |
| `api` | 直连大模型 API 的 agent 循环：内置 4 个工具（列目录 / 读文件 / 写文件 / 跑命令），流式进度、用量取自 API 返回 |

```jsonc
{
  "engine": "api",
  "engines": {
    "api": {
      "model": "deepseek-chat",
      "baseUrl": "https://api.deepseek.com/v1",
      "apiKeyEnv": "DEEPSEEK_API_KEY"
    }
  }
}
```

> 引擎名写错会直接报错，不会静默退回 dsh。设计说明与两套实现的差异对照见 [docs/引擎解耦设计.md](docs/引擎解耦设计.md)。

---

## 配置与数据

**优先级：环境变量 > `opc-config.json` > 默认值**（配置文件不入库）。

| 字段 | 默认 | 说明 |
|---|---|---|
| `root` | 项目根 | 总根目录，其下自动生成 批阅台 / 工作区 / 知识库 |
| `port` | `8901` | 监听端口（**改后需重启**） |
| `engine` | `dsh` | 执行引擎名（见上节） |
| `model` | — | `{provider, apiKeyEnv?, baseURL?, model?}`；**密钥不写这里** |
| `schedule` | `[]` | 定时任务（每天 / 每周 / 每隔 N 分钟） |
| `pollSeconds` | `8` | 调度守护轮询间隔（秒） |
| `maxSubtasks` | `2` | 单任务最多拆成几个子任务 |

**环境变量**：`OPC_CONFIG`（配置文件路径）、`OPC_KB_ROOT`（知识库根）、`OPC_PORT`（端口）、`OPC_ENGINE`（引擎）。

| 数据 | 落地 |
|---|---|
| API 凭据 | 只写项目根 `.env`；不进配置、不回显、不入库 |
| 台账 | `批阅台/opc.db`（SQLite）：任务 / 子任务 / 回报，唯一真相 |
| 产物 | `工作区/<角色名>/T-xxx-Sn-report.md` + 同名 `.meta.json`；完成后移入 `已归档/` |
| 运行数据 | 批阅台 / 工作区 / 知识库启动时幂等生成，**不入库**，仓库保持干净 |

---

## 开发与测试

- 标准 src 布局：包在 `src/opc_web/`（config / server / scheduler / chain / store / agent / roles / review / engines），测试在 `tests/`；
- 控制台零 pip 依赖；执行闭环需 dsh（或改用 `api` 引擎）；
- 角色管理 CLI：`python -m opc_web roles list | add --name … --duty …`；

```bash
python -m unittest discover -s tests -v
```

---

## 支持与致谢

如果这个项目对你有帮助，欢迎在仓库右上角**点一个 ⭐ Star**——让更多「一人公司」和独立开发者看到它，就是最好的支持：

<p align="center">
  <img src="images/alipay.png" alt="支付宝赞赏码" width="200">
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="images/wechatpay.png" alt="微信赞赏码" width="200">
</p>

---

## 许可证

[MIT License](LICENSE)
