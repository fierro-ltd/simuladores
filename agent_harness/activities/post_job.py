"""Post-job learning Temporal activity types — Phase 6."""

import re
from dataclasses import dataclass

from agent_harness.memory.graph import MemoryType
from agent_harness.memory.graph_store import InMemoryGraphStore


@dataclass(frozen=True)
class PostJobInput:
    """Input for the post-job learning activity."""
    operativo_id: str
    domain: str
    session_progress: str  # Full PROGRESS.md content


@dataclass(frozen=True)
class PostJobOutput:
    """Output from the post-job learning activity."""
    operativo_id: str
    patterns_extracted: int
    archived: bool


# Regex to split PROGRESS.md into phase sections
_PHASE_RE = re.compile(r"^## (\w+) — (\w+)\s*\n\n(.+?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL)


async def extract_patterns(
    store: InMemoryGraphStore,
    domain: str,
    operativo_id: str,
    session_progress: str,
) -> int:
    """Extract learning patterns from a completed operativo's progress log.

    Parses PROGRESS.md sections, stores each phase outcome as a typed memory node.
    Returns the number of patterns extracted.
    """
    if not session_progress.strip():
        return 0

    sections = _PHASE_RE.findall(session_progress)
    count = 0

    for phase_name, agent, report in sections:
        report = report.strip()
        if not report:
            continue

        # Determine memory type from content
        if "NEEDS_REVIEW" in report:
            mtype = MemoryType.ERROR
            importance = 0.7
        elif "status=COMPLETED" in report:
            mtype = MemoryType.PATTERN
            importance = 0.5
        else:
            mtype = MemoryType.FACT
            importance = 0.4

        await store.store(
            domain=domain,
            content=report,
            memory_type=mtype,
            importance=importance,
            source=operativo_id,
            metadata={"phase": phase_name, "agent": agent},
        )
        count += 1

    return count
