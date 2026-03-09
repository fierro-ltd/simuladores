"""Tests for production configuration."""

import os
import pytest

from agent_harness.config import (
    VertexConfig,
    TemporalConfig,
    StorageConfig,
    SandboxConfig,
    AppConfig,
    load_config,
)


class TestVertexConfig:
    def test_defaults(self):
        config = VertexConfig()
        assert config.project_id == ""
        assert config.region == "europe-west1"
        assert config.max_retries == 3
        assert config.timeout_seconds == 120
        assert config.compaction_model == "compact-2026-01-12"

    def test_frozen(self):
        config = VertexConfig()
        with pytest.raises(AttributeError):
            config.project_id = "secret"


class TestTemporalConfig:
    def test_defaults(self):
        config = TemporalConfig()
        assert config.host == "localhost:7233"
        assert config.namespace == "default"
        assert config.tls_enabled is False


class TestStorageConfig:
    def test_defaults(self):
        config = StorageConfig()
        assert config.backend == "local"
        assert config.gcs_bucket == ""


class TestSandboxConfig:
    def test_defaults(self):
        config = SandboxConfig()
        assert config.backend == "docker"
        assert config.timeout_seconds == 10
        assert config.memory_mb == 128


class TestAppConfig:
    def test_defaults(self):
        config = AppConfig()
        assert config.environment == "development"
        assert config.log_level == "INFO"
        assert isinstance(config.vertex, VertexConfig)
        assert isinstance(config.temporal, TemporalConfig)


class TestLoadConfig:
    def test_defaults(self):
        config = load_config()
        assert config.environment == "development"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("HARNESS_ENVIRONMENT", "production")
        monkeypatch.setenv("HARNESS_LOG_LEVEL", "DEBUG")
        config = load_config()
        assert config.environment == "production"
        assert config.log_level == "DEBUG"

    def test_vertex_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project-123")
        monkeypatch.setenv("VERTEX_REGION", "us-central1")
        monkeypatch.setenv("ANTHROPIC_MAX_RETRIES", "5")
        config = load_config()
        assert config.vertex.project_id == "my-project-123"
        assert config.vertex.region == "us-central1"
        assert config.vertex.max_retries == 5

    def test_temporal_tls(self, monkeypatch):
        monkeypatch.setenv("TEMPORAL_TLS", "true")
        config = load_config()
        assert config.temporal.tls_enabled is True

    def test_storage_gcs(self, monkeypatch):
        monkeypatch.setenv("HARNESS_STORAGE_BACKEND", "gcs")
        monkeypatch.setenv("HARNESS_STORAGE_GCS_BUCKET", "my-bucket")
        config = load_config()
        assert config.storage.backend == "gcs"
        assert config.storage.gcs_bucket == "my-bucket"

    def test_sandbox_monty(self, monkeypatch):
        monkeypatch.setenv("HARNESS_SANDBOX_BACKEND", "monty")
        config = load_config()
        assert config.sandbox.backend == "monty"
