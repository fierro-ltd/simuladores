"""Base agent configuration and class.

Defines AgentConfig, the AGENT_MODELS registry, logical role mapping,
and BaseAgent which delegates prompt assembly to PromptBuilder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import os as _os

from agent_harness.prompt.builder import PromptBuilder

if TYPE_CHECKING:
    from agent_harness.core.provider_config import ProviderConfig


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""

    name: str
    model: str
    system_identity: str
    domain: str
    max_turns: int = 10
    reasoning_effort: str = "high"


# Model assignments are hardcoded, not configurable.

# Override all models via env var for local dev/testing (Opus can be very slow on Vertex AI)
_DEV_MODEL = _os.environ.get("HARNESS_DEV_MODEL")
AGENT_MODELS: dict[str, str] = {
    "santos": _DEV_MODEL or "claude-sonnet-4-6",
    "medina": _DEV_MODEL or "claude-sonnet-4-6",
    "lamponne": _DEV_MODEL or "claude-sonnet-4-6",
    "ravenna": _DEV_MODEL or "claude-sonnet-4-6",
}

# Reasoning effort per agent — "reasoning sandwich" pattern.
# High for planning/verification (Santos, Medina), medium for execution/assembly.
AGENT_EFFORTS: dict[str, str] = {
    "santos": "high",       # Planning + QA need deep reasoning
    "medina": "high",       # Injection scanning needs care
    "lamponne": "medium",   # Executing a known plan
    "ravenna": "medium",    # Assembly, not reasoning
}

# Logical role mapping — agents use roles, provider config resolves to model strings.
AGENT_ROLES: dict[str, str] = {
    "santos": "capable",      # Planning + QA need strong reasoning
    "medina": "capable",      # Injection scanning needs top-tier reasoning
    "lamponne": "fast",       # Executing a known plan
    "ravenna": "fast",        # Assembly, not reasoning
}


def resolve_agent_model(agent_name: str, provider: ProviderConfig | None = None) -> str:
    """Resolve an agent's model string.

    If provider config is given, resolves via logical roles.
    Falls back to AGENT_MODELS for backward compatibility.
    """
    if provider is not None:
        role = AGENT_ROLES[agent_name]
        return provider.resolve_model(role)
    return AGENT_MODELS[agent_name]


class BaseAgent:
    """Base agent that assembles prompts via PromptBuilder.

    Subclasses override system_identity and may add tools.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def build_prompt(
        self,
        user_message: str,
        domain_memory: str = "",
        semantic_patterns: list[str] | None = None,
        session_state: str = "",
    ) -> dict[str, Any]:
        """Build a prompt dict using PromptBuilder in strict layer order."""
        builder = PromptBuilder()
        builder.set_system_identity(self.config.system_identity)
        builder.set_domain_memory(domain_memory)
        builder.set_semantic_patterns(semantic_patterns or [])
        builder.set_session_state(session_state)
        builder.add_working_message(role="user", content=user_message)
        return builder.build()
