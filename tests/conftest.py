"""Shared test fixtures for agent-harness."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_storage(tmp_path: Path) -> Path:
    """Temporary directory for storage backend tests."""
    return tmp_path / "storage"


@pytest.fixture
def sample_cpc_dir() -> Path:
    """Path to sample DCE test data, if available."""
    path = Path(os.environ.get("CPC_DATA_DIR", "tests/fixtures"))
    return path


@pytest.fixture
def operativo_id() -> str:
    """A deterministic operativo ID for tests."""
    return "test-operativo-001"
