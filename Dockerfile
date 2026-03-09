# Development Dockerfile — for quick local iteration.
# For production deployment, use infra/Dockerfile.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY agent_harness/ agent_harness/

# Default command (overridden by docker-compose)
CMD ["python", "-m", "agent_harness.gateway"]
