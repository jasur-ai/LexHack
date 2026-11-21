# Single-image haqli: the React app is built in the first stage and served by the FastAPI backend (same origin, so
# the /api SSE stream and the /ws WebSocket need no proxy). docker-compose.yml keeps using backend/ and web/ images.
#   docker build -t haqli haqli && docker run -p 8002:8002 -e AGENT_BASE_URL=http://host.docker.internal:8000 haqli

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STORAGE_DIR=/app/storage

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-core \
    fonts-dejavu-core \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-uzb \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ ./
COPY scripts/ /app/scripts/
COPY --from=web /web/dist /app/web/dist
RUN mkdir -p /app/storage/pdfs /app/storage/uploads

EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8002\")}/healthz', timeout=4)"

# On Render, PORT and RENDER_EXTERNAL_URL are provided; the public URL is used for PDF QR codes and CORS unless
# PUBLIC_BASE_URL / CORS_ORIGINS are set explicitly.
CMD ["sh", "-c", "export PUBLIC_BASE_URL=\"${PUBLIC_BASE_URL:-${RENDER_EXTERNAL_URL:-http://localhost:${PORT:-8002}}}\"; export CORS_ORIGINS=\"${CORS_ORIGINS:-$PUBLIC_BASE_URL}\"; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8002} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30"]
