# 一行跑起来（本地优先：容器里必须显式让端口对外可达）：
#
#   docker build -t opc-web .
#   docker run --rm -p 8901:8901 -v opc-data:/data \
#     -e DEEPSEEK_API_KEY=sk-...      \
#     opc-web
#
# 数据（批阅台 / 工作区 / 知识库）全在 /data 卷里；密钥也可以起来后在
# 「设置 → 模型接入」里填，它会写进容器内的 .env（想持久化就把 /app/.env 也挂出去）。
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# 唯一的第三方依赖：解 DSH 会话日志（读用量与心跳）。纯直连 API 引擎时用不到。
RUN pip install --no-cache-dir zstandard

ENV OPC_HOST=0.0.0.0 \
    OPC_KB_ROOT=/data \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8901

CMD ["python", "run.py"]
