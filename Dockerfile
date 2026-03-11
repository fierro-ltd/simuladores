# Development Dockerfile — for quick local iteration.
# For production deployment, use infra/Dockerfile.
FROM python:3.11-slim

WORKDIR /app

# Copy source and install
COPY pyproject.toml .
COPY agent_harness/ agent_harness/
RUN pip install --no-cache-dir .

# Default command (overridden by docker-compose)
CMD ["python", "-m", "agent_harness.gateway"]
