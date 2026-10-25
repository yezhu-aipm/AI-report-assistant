# 学情报告助手：前端打包 + 后端 + Chromium（生成 PDF）+ 中文字体，一个镜像跑全部服务
# 国内服务器构建时默认使用国内镜像源；在海外构建可以把下面几个 ARG 改成官方源

# ---------- 1. 打包前端 ----------
FROM node:20-bookworm-slim AS web
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm config set registry $NPM_REGISTRY && npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. 后端运行环境 ----------
FROM python:3.12-slim-bookworm
ARG APT_MIRROR=mirrors.aliyun.com
ARG PIP_INDEX=https://mirrors.aliyun.com/pypi/simple
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Shanghai \
    DATA_DIR=/data FRONTEND_DIR=/app/frontend/dist PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN if [ -n "$APT_MIRROR" ]; then sed -i "s/deb.debian.org/$APT_MIRROR/g" /etc/apt/sources.list.d/debian.sources; fi \
 && apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk fontconfig tzdata \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -i $PIP_INDEX -r requirements.txt \
 && PLAYWRIGHT_DOWNLOAD_HOST=$PLAYWRIGHT_DOWNLOAD_HOST python -m playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
