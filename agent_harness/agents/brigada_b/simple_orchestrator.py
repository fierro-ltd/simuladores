"""SimpleOrchestrator — lightweight agent for simple operativos.

Combines plan + execute in one pass. Used when Santos determines
at planning time that the operativo is a single-phase retrieval
or format conversion.

No Medina investigation (input already trusted).
No QA loop (output is deterministic format conversion).
Still writes PROGRESS.md for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_harness.agents.base import BaseAgent, AgentConfig, AGENT_MODELS


SIMPLE_ORCHESTRATOR_IDENTITY = """You are a SimpleOrchestrator from Brigada B.

Your role is to handle simple operativos that don't require
the full four-agent pipeline. You combine planning and execution
in a single pass.

## When You Are Used
- Single-phase retrieval tasks
- Format conversion tasks
- Tasks where Santos determined complexity is "simple"

## Rules
- Complete the task in a single pass
- Write a PROGRESS.md field report for auditability
- No investigation needed (input is trusted)
- No QA loop (output is deterministic)
- Still follow domain tool restrictions
"""


@dataclass(frozen=True)
class SimpleOrchestratorConfig:
    """Configuration for a simple operativo."""
    domain: str
    max_turns: int = 5
    model: str = "claude-sonnet-4-6"


def is_simple_operativo(plan_complexity: str) -> bool:
    """Check if an operativo should use Brigada B.

    Santos's plan output includes complexity: "simple" | "standard".
    """
    return plan_complexity == "simple"
