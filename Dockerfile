FROM node:24-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime

ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="Synergy Learning Intelligence" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.source="https://github.com/aswinkp/synergy-poc"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATABASE_PATH=/app/data/learning_chat.db \
    EXPORTS_PATH=/app/data/exports \
    EXCEL_PATH=/app/input/learning.xlsx \
    HEADCOUNT_EXCEL_PATH=/app/input/headcount.xlsx

WORKDIR /app
RUN groupadd --gid 10001 synergy \
    && useradd --uid 10001 --gid synergy --create-home --home-dir /home/synergy synergy

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist/

RUN mkdir -p /app/data/exports /app/input \
    && chown -R synergy:synergy /app /home/synergy

USER synergy
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).read()"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
