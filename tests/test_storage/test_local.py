"""Tests for local storage backend."""

import pytest

from agent_harness.storage.backend import StorageBackend
from agent_harness.storage.local import LocalStorageBackend


@pytest.fixture
def backend(tmp_path):
    return LocalStorageBackend(root=tmp_path)


class TestLocalStorageBackend:
    async def test_implements_protocol(self, backend):
        assert isinstance(backend, StorageBackend)

    async def test_write_and_read(self, backend):
        await backend.write("test/file.txt", b"hello world")
        data = await backend.read("test/file.txt")
        assert data == b"hello world"

    async def test_read_nonexistent_raises(self, backend):
        with pytest.raises(FileNotFoundError):
            await backend.read("nonexistent.txt")

    async def test_exists_true(self, backend):
        await backend.write("exists.txt", b"data")
        assert await backend.exists("exists.txt") is True

    async def test_exists_false(self, backend):
        assert await backend.exists("nope.txt") is False

    async def test_list_prefix(self, backend):
        await backend.write("prefix/a.txt", b"a")
        await backend.write("prefix/b.txt", b"b")
        await backend.write("other/c.txt", b"c")
        keys = await backend.list("prefix")
        assert sorted(keys) == ["prefix/a.txt", "prefix/b.txt"]

    async def test_write_creates_parent_dirs(self, backend):
        await backend.write("deep/nested/dir/file.txt", b"data")
        data = await backend.read("deep/nested/dir/file.txt")
        assert data == b"data"

    async def test_overwrite_existing(self, backend):
        await backend.write("file.txt", b"old")
        await backend.write("file.txt", b"new")
        data = await backend.read("file.txt")
        assert data == b"new"

    async def test_list_empty_prefix(self, backend):
        keys = await backend.list("nonexistent_prefix")
        assert keys == []
