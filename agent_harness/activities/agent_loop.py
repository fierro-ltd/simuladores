"""Agent loop activity input/output types for Temporal activities."""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AgentLoopInput:
    """Input for the agent loop activity."""

    agent_name: str
    domain: str
    operativo_id: str
    task_message: str
    available_tools: List[str]
    max_turns: int = 10


@dataclass(frozen=True)
class AgentLoopOutput:
    """Output from the agent loop activity."""

    final_response: str
    tool_calls_made: List[str]
    turns_used: int
