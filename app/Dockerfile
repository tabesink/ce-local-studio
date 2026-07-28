FROM python:3.12-slim AS runtime

ARG CE_STACK_LIVE_IMAGE=0
ARG CE_STACK_OBJECT_STORE_IMAGE=0

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock alembic.ini ./
COPY migrations ./migrations
COPY context_engine ./context_engine
COPY vendor ./vendor

# Default slim image: package only.
# Live overlay (CE_STACK_LIVE_IMAGE=1): Docker CLI + LightRAG runtime extras.
# MinIO overlay (CE_STACK_OBJECT_STORE_IMAGE=1): boto3 object-store extra.
RUN python -m pip install --no-cache-dir uv==0.8.9 \
    && if [ "$CE_STACK_LIVE_IMAGE" = "1" ]; then \
         apt-get update \
         && apt-get install -y --no-install-recommends ca-certificates docker.io \
         && rm -rf /var/lib/apt/lists/*; \
       fi \
    && if [ "$CE_STACK_LIVE_IMAGE" = "1" ] && [ "$CE_STACK_OBJECT_STORE_IMAGE" = "1" ]; then \
         uv sync --frozen --no-dev --extra lightrag-runtime --extra object-store; \
       elif [ "$CE_STACK_LIVE_IMAGE" = "1" ]; then \
         uv sync --frozen --no-dev --extra lightrag-runtime; \
       elif [ "$CE_STACK_OBJECT_STORE_IMAGE" = "1" ]; then \
         uv sync --frozen --no-dev --extra object-store; \
       else \
         uv sync --frozen --no-dev; \
       fi

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "context_engine.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
