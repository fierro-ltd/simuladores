"""Tests for session store."""

import pytest

from agent_harness.core.operativo import Phase
from agent_harness.core.plan import PhaseResult
from agent_harness.memory.session_store import SessionStore
from agent_harness.storage.local import LocalStorageBackend


@pytest.fixture
def backend(tmp_path):
    return LocalStorageBackend(root=tmp_path)


@pytest.fixture
def session_store(backend):
    return SessionStore(backend=backend, operativo_id="test-op-001")


class TestSessionStore:
    async def test_save_and_read_plan(self, session_store):
        await session_store.save_plan('{"tasks": []}')
        plan = await session_store.read_plan()
        assert plan == '{"tasks": []}'

    async def test_append_and_read_progress(self, session_store):
        result = PhaseResult(phase=Phase.PLAN, agent="santos", field_report="Planning done.")
        await session_store.append_progress(result)
        progress = await session_store.read_progress()
        assert "PLAN" in progress
        assert "santos" in progress
        assert "Planning done." in progress

    async def test_multiple_field_reports(self, session_store):
        r1 = PhaseResult(phase=Phase.PLAN, agent="santos", field_report="Plan complete.")
        r2 = PhaseResult(phase=Phase.INVESTIGATE, agent="medina", field_report="Docs read.")
        await session_store.append_progress(r1)
        await session_store.append_progress(r2)
        progress = await session_store.read_progress()
        assert "PLAN" in progress
        assert "INVESTIGATE" in progress
        assert "Plan complete." in progress
        assert "Docs read." in progress

    async def test_empty_progress(self, session_store):
        progress = await session_store.read_progress()
        assert progress == ""

    async def test_missing_plan_raises(self, session_store):
        with pytest.raises(FileNotFoundError):
            await session_store.read_plan()
