#!/usr/bin/env sh
# macOS / Linux 启动入口（等价于 Windows 的「启动控制台.bat」）：
#   sh run.sh
# 首次运行前：pip install zstandard（只走直连 API 引擎的话可以不装）
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || { echo "找不到 $PY，请先装 Python 3.9+"; exit 1; }
echo "OPC 智能体工作台（opc-web）正在启动 ..."
echo "  地址：见下方启动日志（端口取自 opc-config.json，默认 8901）"
echo "  首次启动自动生成 批阅台/ 工作区/ 知识库/ 三目录（运行数据不入库）"
exec "$PY" run.py
