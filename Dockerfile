# syntax=docker/dockerfile:1.6
#
# Multi-stage Dockerfile for the Intelligent Profiling Engine.
# Stage 1: build / install deps. Stage 2: slim runtime image.
ARG PYTHON_VERSION=3.12-slim

FROM python:${PYTHON_VERSION} AS builder

WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build deps for numpy / scikit-learn wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && pip install --prefix=/install -r requirements.txt

# ---------------------------------------------------------------- runtime ---
FROM python:${PYTHON_VERSION} AS runtime

LABEL org.opencontainers.image.title="intelligent-profiling-engine" \
      org.opencontainers.image.source="https://github.com/bucky-ops/intelligent-profiling-engine" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Bring installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy source.
COPY src/ ./src/
COPY app.py gui_app.py run.py run_synthetic.py ./
COPY config/ ./config/
COPY examples/ ./examples/

# Pre-download the spaCy model so first request isn't slow.
RUN python -m spacy download en_core_web_sm || true

# Volume for profiles.json + synthetic data.
RUN mkdir -p /app/data && useradd -m -u 1000 iprofile
USER iprofile
VOLUME ["/app/data"]
ENV PROFILES_STORAGE_PATH=/app/data/profiles.json \
    LOG_LEVEL=INFO \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3); sys.exit(0)" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
