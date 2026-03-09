"""Production configuration — environment-based.

Loads configuration from environment variables with sensible defaults.
No secrets in code — all sensitive values from environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VertexConfig:
    """Vertex AI configuration for Claude models."""
    project_id: str = ""
    region: str = "europe-west1"
    max_retries: int = 3
    timeout_seconds: int = 120
    compaction_model: str = "compact-2026-01-12"


@dataclass(frozen=True)
class TemporalConfig:
    """Temporal server configuration."""
    host: str = "localhost:7233"
    namespace: str = "default"
    tls_enabled: bool = False


@dataclass(frozen=True)
class StorageConfig:
    """Storage backend configuration."""
    backend: str = "local"  # "local" / "gcs"
    local_path: str = "/tmp/agent-harness"
    gcs_bucket: str = ""


@dataclass(frozen=True)
class SandboxConfig:
    """Sandbox configuration."""
    backend: str = "docker"  # "docker" / "monty"
    timeout_seconds: int = 10
    memory_mb: int = 128


@dataclass(frozen=True)
class GatewayConfig:
    """Gateway security configuration."""
    api_keys: str = ""  # empty = auth disabled
    rate_limit_max: int = 0  # 0 = disabled
    rate_limit_window: int = 60


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""
    environment: str = "development"
    log_level: str = "INFO"
    vertex: VertexConfig = VertexConfig()
    temporal: TemporalConfig = TemporalConfig()
    storage: StorageConfig = StorageConfig()
    sandbox: SandboxConfig = SandboxConfig()
    gateway: GatewayConfig = GatewayConfig()


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    return AppConfig(
        environment=os.getenv("HARNESS_ENVIRONMENT", "development"),
        log_level=os.getenv("HARNESS_LOG_LEVEL", "INFO"),
        vertex=VertexConfig(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            region=os.getenv("VERTEX_REGION", "europe-west1"),
            max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "3")),
            timeout_seconds=int(os.getenv("ANTHROPIC_TIMEOUT", "120")),
        ),
        temporal=TemporalConfig(
            host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            tls_enabled=os.getenv("TEMPORAL_TLS", "false").lower() == "true",
        ),
        storage=StorageConfig(
            backend=os.getenv("HARNESS_STORAGE_BACKEND", "local"),
            local_path=os.getenv("HARNESS_STORAGE_LOCAL_PATH", "/tmp/agent-harness"),
            gcs_bucket=os.getenv("HARNESS_STORAGE_GCS_BUCKET", ""),
        ),
        sandbox=SandboxConfig(
            backend=os.getenv("HARNESS_SANDBOX_BACKEND", "docker"),
            timeout_seconds=int(os.getenv("HARNESS_SANDBOX_TIMEOUT", "10")),
            memory_mb=int(os.getenv("HARNESS_SANDBOX_MEMORY_MB", "128")),
        ),
        gateway=GatewayConfig(
            api_keys=os.getenv("HARNESS_API_KEYS", ""),
            rate_limit_max=int(os.getenv("HARNESS_RATE_LIMIT_MAX", "0")),
            rate_limit_window=int(os.getenv("HARNESS_RATE_LIMIT_WINDOW", "60")),
        ),
    )
