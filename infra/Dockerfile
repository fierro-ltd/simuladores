# ============================================================
# Agent Harness — Production Dockerfile
# ============================================================
# Multi-stage build for minimal image size.
# Target: GCE VM with Docker / Cloud Run.
# ============================================================

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed for some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY agent_harness/ agent_harness/
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.11-slim

# System deps for pypdfium2 rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --shell /bin/bash harness

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY agent_harness/ agent_harness/

# Create data directory with correct ownership
RUN mkdir -p /data && chown harness:harness /data && chown -R harness:harness /app

# ADC credentials mount point
# Mount at runtime: -v ~/.config/gcloud/application_default_credentials.json:/tmp/adc.json:ro
ENV GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json

# Storage root
ENV STORAGE_ROOT=/data

# Switch to non-root user
USER harness

# Health check for gateway mode
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

EXPOSE 8000

# Default: run gateway. Override for worker.
ENTRYPOINT ["python", "-m"]
CMD ["agent_harness.gateway"]
