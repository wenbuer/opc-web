# OPC Console (opc-web)

[简体中文](README.md) · English

[![tests](https://github.com/wenbuer/opc-web/actions/workflows/test.yml/badge.svg)](https://github.com/wenbuer/opc-web/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![runtime](https://img.shields.io/badge/runtime-stdlib%20%2B%20zstandard-brightgreen.svg)](pyproject.toml)
[![engine](https://img.shields.io/badge/engine-API%20%7C%20DSH-blueviolet.svg)](#execution-engines)
[![network](https://img.shields.io/badge/network-127.0.0.1%20only-purple.svg)](#configuration-and-data)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

opc-web is a locally-run console for managing a team of AI worker agents. It keeps the whole life of a task — assignment, decomposition, execution, reporting, review, archiving — inside a single interface.

Roles come in three levels:

- **R0** — the human. Sets direction, carries the spend, approves.
- **R1** — the assistant. Decomposes tasks, decides when to dispatch them (by priority and by peak/off-peak pricing), consolidates reports, extracts the decisions that need a human, and archives.
- **RX** — worker agents. Each carries a role card and mounted skills, works with tools inside the project workspace, and writes a report.

Worker tasks run on a swappable execution engine: direct LLM API calls by default, or DSH (DeepSeek Harness) headless.

Requirements and boundaries:

- Python 3.9+. The only third-party dependency is `zstandard`, used to read DSH session logs for usage and heartbeat; everything else is the standard library.
- Task state lives in a local SQLite database; deliverables and knowledge entries are Markdown files. The console binds `127.0.0.1` only.
- All run data stays in the project directory on your machine; nothing is sent to an external service.

## Preview

<table>
<tr>
<td width="25%"><img src="images/opc-command-center-01.png" alt="Command panel"><br><sub>Command panel · overview</sub></td>
<td width="25%"><img src="images/opc-command-center-02.png" alt="Review desk"><br><sub>Review desk · decisions</sub></td>
<td width="25%"><img src="images/opc-command-center-03.png" alt="Workbench"><br><sub>Workbench · board and live events</sub></td>
<td width="25%"><img src="images/opc-command-center-04.png" alt="Run log"><br><sub>Run log · full trace</sub></td>
</tr>
<tr>
<td width="25%"><img src="images/opc-command-center-05.png" alt="Project files"><br><sub>Project files · artifacts</sub></td>
<td width="25%"><img src="images/opc-command-center-06.png" alt="Knowledge base"><br><sub>Knowledge base</sub></td>
<td width="25%"><img src="images/opc-command-center-07.png" alt="Daily brief"><br><sub>Daily brief</sub></td>
<td width="25%"><img src="images/opc-command-center-08.png" alt="Token stats"><br><sub>Settings · token usage</sub></td>
</tr>
</table>

## Contents

- [Overview](#overview)
- [Preview](#preview)
- [How it works](#how-it-works)
- [Features](#features)
- [Quick start](#quick-start)
- [Interface](#interface)
- [Execution engines](#execution-engines)
- [Configuration and data](#configuration-and-data)
- [Development and tests](#development-and-tests)
- [Contributing](#contributing)
- [License](#license)

## How it works

<p align="center">
  <img src="images/opc-task-loop-01.png" alt="Task loop: task → roles → interpretation, back to task" width="880">
  <br>
  <em>Task loop: the human appears at ① assignment and ⑧ review (red); ②③⑥⑦ are R1's work (blue); ④⑤ are executed by the RX roles (purple).</em>
</p>

| Stage | Owner | What happens |
|---|---|---|
| Task | R0 · R1 | The human states what is needed; R1 splits it into independently deliverable subtasks and decides when each may start, by priority and by peak/off-peak pricing |
| Roles | RX | Worker agents use tools inside the project, write deliverables into the workspace and file a report |
| Interpretation | R1 · R0 | R1 consolidates the reports and raises the decisions that need a human; R0 reviews. Your annotation becomes the next instruction |

When a round finishes, deliverables land in both the ledger and the knowledge base; the conclusion of one round becomes the input to the next.

## Features

### Tasks and dispatch

- **Automatic decomposition**: one line becomes 1–3 independently deliverable subtasks, each naming a role and the expected deliverable; a named role can also be dispatched directly.
- **Queue priority**: pending subtasks can be marked high / normal / low; task selection and in-task ordering follow it.
- **Peak / off-peak scheduling**: peak hours are weekdays 09:00–12:00 and 14:00–18:00 (unit prices double); tasks of two or more subtasks wait for an off-peak window. "Run now" bypasses deferral and moves the task to the front.
- **Scheduled tasks**: daily / weekly / every N minutes.

### Execution engines and guardrails

- **Swappable engines**: direct LLM API by default, or DSH (DeepSeek Harness) headless, with fallback to the secondary engine when the primary fails.
- **Skills**: skills live in a shared library and are mounted by registering them on a role card; they are independent of the engine.
- **Visibility while running**: role cards show the current task; the workbench has a four-column board (pending / dispatched / done / blocked) and a live event stream.
- **Execution guardrails**: a single run is capped at 300 rounds, 320 tool calls and 30M cumulative input tokens; exceeding a cap stops the run, which is filed as blocked.
- **No silent failures**: exceptions in archiving, metadata and wrap-up paths are recorded in the event stream.

### Reports, review and knowledge

- **Reports on disk**: output is written to `工作区/<role>/T-xxx-Sn-report.md` plus a matching `.meta.json`; on completion the body moves to `已归档/` and the report enters the ledger.
- **Review drives execution**: approving creates an "execute the R0 decision" task, rejecting redoes the work with your annotation; the review desk has three sections: work items / decisions / archived.
- **Decisions kept separate**: every task appears under work items; only items that need a call get an extra "decision N" entry.
- **Knowledge base**: R1 decides whether anything is worth keeping; entries are filed by topic and merged into existing documents, each with OKF front-matter.
- **Daily brief**: tasks of the day are summarised automatically, with a structural check before writing.

### Cost and scheduling

- **Three-tier pricing**: fresh input, cache hit and output are metered separately; the home view shows totals and today's figures.
- **Run switches**: the R1 assistant dock and peak deferral of long tasks are collected under Settings → run switches.

### Running and deployment

- **Local-first**: SQLite and Markdown, bound to localhost.
- **Minimal dependencies**: everything but `zstandard` is the standard library.
- **Entry points**: `run.py`; `启动控制台.bat` on Windows, `run.sh` on macOS / Linux.
- **Themes**: light and dark.

## Quick start

**Requirements**: Python 3.9+ (Windows, macOS and Linux are all exercised in CI). Optional dependency `zstandard` — only the DSH engine needs it to read session logs; a direct-API-only setup can skip it.

```bash
git clone https://github.com/wenbuer/opc-web.git
cd opc-web
pip install zstandard        # optional
python run.py                # → http://127.0.0.1:8901 (opens your browser)
```

On Windows you can also double-click `启动控制台.bat`; on macOS / Linux run `sh run.sh`. Both are thin wrappers around `python run.py`.

**Docker** (data lives in the `opc-data` volume; inside a container the bind address must be set explicitly):

```bash
docker build -t opc-web .
docker run --rm -p 8901:8901 -v opc-data:/data -e DEEPSEEK_API_KEY=sk-... opc-web
```

First three steps:

1. Open http://127.0.0.1:8901 (directories and skeleton files are created on first start).
2. Under Settings → Model, enter your API key and the three unit prices (or copy `.env.example` to `.env` and fill it in manually).
3. Assign your first task from the command panel or the workbench.

> Not published on PyPI yet. Bundled assets (`templates/`, `static/`, `agents-seed/`) are not packaged into a wheel, so please install by cloning as shown above.

## Interface

| View | Purpose |
|---|---|
| **Command panel** | Org chart, role card status and project timeline; overview strip with task states (todo / running / done), token usage (including today), project cost (including today), knowledge file count and latest brief |
| **Workbench** | Task assignment, four-column subtask board (with priority chips and "run now" on the pending column), task detail and live event stream |
| **Review desk** | Approve / reject / amend reports; decisions drive the next dispatch. Three independently scrolling sections: work items / decisions / archived |
| **Project files** | Deliverables filtered by role / project / task, defaulting to the `项目/` engineering area; Markdown rendering, inline HTML preview and full screen |
| **Knowledge base** | Entries grouped by category, each card showing type and create / update / source task |
| **Daily brief** | Summaries generated from the day's tasks |
| **Settings** | Project selection, execution engine, model access (including the three unit prices and peak/off-peak hints), scheduled tasks, token statistics, skill import, run switches |

## Execution engines

The engine that runs worker tasks is swappable and configured in `opc-config.json`:

| Engine | Description |
|---|---|
| `api` (default) | An agent loop over direct LLM API calls with four built-in tools (list directory / read file / write file / run command). Progress is streamed and usage comes from API responses; provider and key come from Settings → Model |
| `dsh` | Runs `dsh --profile headless`. Brings its own tool sandbox and skill ecosystem; usage and progress are read from session logs |

```jsonc
{
  "engine": "dsh",                  // primary engine (api | dsh)
  "engineFallback": "api",          // used when the primary engine fails to start
  "engineFor": {                    // per-purpose routing; empty means use the primary
    "prompt": "api",                //   light text reasoning: decomposition / consolidation
    "execute": "dsh"                //   worker task execution
  },
  "model": { "provider": "deepseek" }   // model access: the api engine reuses this
}
```

Changes take effect on page refresh, no restart needed. Settings → Execution engine only reports the current engine and its availability (including the config file path); there is no switch there, because engine selection is a config-file decision.

A few notes:

- An unknown engine name raises an error instead of silently falling back;
- **Per-purpose routing**: `engineFor` can pick different engines for `prompt` (decomposition / consolidation) and `execute` (worker tasks);
- **Skills are engine-independent**: imported skills go into the shared library, are mounted by role cards and are spliced into the role prompt; both engines use the same set, differing only in whether they can execute the commands and read/write steps inside a skill;
- **Capabilities are declared truthfully**: an engine reports whether it supports limits such as a step cap (DSH headless has none, and says so), and the UI degrades accordingly;
- **Failure fallback**: if the primary engine errors or exits immediately with no output, the secondary engine runs the task once more. A long run with no output is treated as a task problem and is not retried; cancellation is not retried either. Every fallback is recorded and visible in the workbench.

> Environment variables `OPC_ENGINE` / `OPC_ENGINE_FALLBACK` take precedence over the config file, and the UI notes this.

## Configuration and data

Precedence: **environment variables > `opc-config.json` > defaults** (the config file is not committed).

| Field | Default | Meaning |
|---|---|---|
| `root` | project root | Top-level root; 批阅台 / 工作区 / 知识库 are created below it |
| `port` | `8901` | Listen port (restart required after changing) |
| `engine` | `api` | Execution engine name (see above) |
| `engineFallback` | `api` | Secondary engine when the primary fails; same as primary disables it |
| `engineFor` | `{}` | Per-purpose routing: `{prompt, execute}`; empty means use the primary |
| `model` | — | `{provider, apiKeyEnv?, baseURL?, model?}`; the key itself is never stored here |
| `priceIn` / `priceCache` / `priceOut` | `1 / 1 / 2` | Unit prices (CNY per million tokens); leaving `priceCache` empty bills cache reads at the input price |
| `peakDefer` | `true` | Defer long tasks during peak hours |
| `assistantDock` | `true` | Floating R1 assistant dock |
| `schedule` | `[]` | Scheduled tasks (actually stored in the project data directory) |
| `pollSeconds` | `8` | Scheduler poll interval (seconds) |
| `decomposeTimeout` | `480` | No-output timeout for headless decomposition (seconds) |
| `maxSubtasks` | `3` | Maximum subtasks per task |
| `fallbackMaxElapsed` | `60` | Seconds below which a run counts as "immediate exit with no output" for fallback |

**Environment variables**: `OPC_CONFIG` (config file path), `OPC_KB_ROOT` (project data root), `OPC_HOST` (bind address, default `127.0.0.1`; set to `0.0.0.0` only for containers), `OPC_PORT`, `OPC_ENGINE`, `OPC_ENGINE_FALLBACK`, `OPC_TOKEN_PRICE_IN` / `_CACHE` / `_OUT`.

| Data | Location |
|---|---|
| API credentials | `.env` in the project root (not in config, never echoed, never committed) |
| Ledger | `批阅台/opc.db` (SQLite): tasks / subtasks / reports / executions |
| Scheduled tasks | `批阅台/定时任务.json` |
| Deliverables | `工作区/<role>/T-xxx-Sn-report.md` + `.meta.json`, moved to `已归档/` on completion |
| Run logs | `批阅台/运行日志/T-xxx-Sn.log` (full trace) |
| Knowledge entries | `知识库/<category>/<title>.md` with OKF front-matter (`type` / `created` / `updated` / `task`) |
| Run data | 批阅台 / 工作区 / 知识库 are created idempotently at startup and are not committed |

## Development and tests

- **Front-end changes**: edits to `static/*.css`, `static/*.js` or `templates/index.html` need no restart — bump the `?v=` query in the reference and hard-refresh. Changes under `src/opc_web/*.py` require a restart.
- **Run the tests**:

```bash
pip install zstandard        # two suites (dsh usage / execution heartbeat) need it
python scripts/run_tests.py  # runs the 18 test files one by one; single files work too
```

- **CI**: `.github/workflows/test.yml` — Windows + Linux × Python 3.9 / 3.13, on pushes to main and on pull requests. On failure it emits `::error` annotations and a job summary, so failing tests and their output are visible in the commit checks without signing in.
- **Packaging**: `scripts/build.ps1` + `scripts/opc-web.spec` (PyInstaller onedir, Windows).

## Contributing

Before opening a pull request:

1. `python scripts/run_tests.py` must pass. If you change behaviour, add a test — every file in `tests/` is a standalone, single-process script with no test-framework dependency, so an existing file can serve as a template;
2. Commit messages should state what changed before, what changed after, and why; releases are summarised in [CHANGELOG.md](CHANGELOG.md);
3. UI changes should include before/after images (put them in `images/` and reference them with relative paths).

Please file bugs and suggestions through [issues](https://github.com/wenbuer/opc-web/issues) (bug report and feature request templates are provided).

## License

[MIT License](LICENSE)
