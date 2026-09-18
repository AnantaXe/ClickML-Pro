# ── Build stage ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

LABEL maintainer="ClickML Team" \
      description="ClickML-Pro – Enterprise MLOps & Data Engineering"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python package
COPY pyproject.toml README.md ./
COPY clickml_pro/ clickml_pro/

# CPU image: core + data only (quantization needs PyTorch / GPU)
RUN pip install --upgrade pip && \
    pip install ".[data]"

# ── Runtime ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin
COPY --from=base /app /app

# Non-root user
RUN useradd -m clickml && chown -R clickml:clickml /app
USER clickml

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["clickml", "serve", "--host", "0.0.0.0", "--port", "8000"]
