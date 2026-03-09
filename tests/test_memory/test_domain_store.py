"""Tests for domain store."""

import pytest

from agent_harness.memory.domain_store import DomainStore, DomainWriteAttemptError
from agent_harness.storage.local import LocalStorageBackend


@pytest.fixture
def backend(tmp_path):
    return LocalStorageBackend(root=tmp_path)


@pytest.fixture
def domain_store(backend):
    return DomainStore(backend=backend, domain="dce")


class TestDomainStore:
    async def test_read_domain_file(self, backend, domain_store, tmp_path):
        # Set up domain file
        domain_dir = tmp_path / "domains" / "dce"
        domain_dir.mkdir(parents=True)
        (domain_dir / "DCE.md").write_text("# DCE Domain\nContent here.")

        content = await domain_store.read()
        assert "DCE Domain" in content

    async def test_read_returns_string(self, backend, domain_store, tmp_path):
        domain_dir = tmp_path / "domains" / "dce"
        domain_dir.mkdir(parents=True)
        (domain_dir / "DCE.md").write_text("hello")

        result = await domain_store.read()
        assert isinstance(result, str)

    async def test_write_is_blocked(self, domain_store):
        with pytest.raises(DomainWriteAttemptError):
            await domain_store.write("should fail")

    async def test_read_missing_raises(self, domain_store):
        with pytest.raises(FileNotFoundError):
            await domain_store.read()
