# Lex.uz legal agent — production image (no torch, no vector DB; fits a 512 MB instance such as Render Starter).
#
#   docker build -t lex-agent .        (from the agent/ folder)
#   docker run -p 8000:8000 -e GEMINI_API_KEY=... lex-agent
#
# The search index (~95 MB SQLite) is built at image build time, so a new container serves in seconds.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first (cached layer); every runtime dependency ships manylinux wheels, no compiler needed
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Code, bundled corpora and models
COPY pyproject.toml README.md ./
COPY lex_agent ./lex_agent
COPY scripts ./scripts
COPY data/corpus ./data/corpus
COPY data/lex_cache ./data/lex_cache
RUN pip install --no-deps -e . \
    && useradd --create-home --uid 10001 app

# Build the index into the image (bundled LawCodex + lex.uz-sync + practical figures)
RUN LLM_PROVIDER=mock LEX_UZ_ENABLE_LIVE_FALLBACK=false lex-agent build-index --force \
    && chown -R app:app /app/data

USER app

# Small-instance defaults: 4 search threads, no per-thread memory map of the index (process RSS stays ~230 MB;
# set SQLITE_READER_MMAP_MB=256 on larger instances for ~10 ms faster answers)
ENV PORT=8000 \
    WEB_CONCURRENCY=1 \
    LLM_PROVIDER=gemini \
    AUTO_BUILD_INDEX=true \
    AGENT_THREADS=4 \
    SQLITE_READER_MMAP_MB=0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'), timeout=4)" || exit 1

# One worker per 512 MB; the event loop handles concurrent requests (answers are I/O bound or <100 ms)
CMD ["sh", "-c", "exec uvicorn lex_agent.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30"]
