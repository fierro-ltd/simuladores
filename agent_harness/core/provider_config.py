"""Provider configuration: maps logical roles to real provider/model strings.

A single env var — SIMULADORES_PROVIDER_PROFILE — selects the active profile.
Profiles live as TOML files under config/providers/ at the project root.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class GatewayType(str, Enum):
    DIRECT = "direct"          # Anthropic SDK via Vertex — current default
    OPENROUTER = "openrouter"  # OpenRouter cloud gateway
    LITELLM = "litellm"        # Self-hosted LiteLLM proxy


@dataclass(frozen=True)
class ProviderConfig:
    """Deployment-time binding between logical roles and model strings."""

    name: str
    gateway: GatewayType
    base_url: str | None
    roles: dict[str, str]   # logical role -> provider/model string
    auth_type: str

    def resolve_model(self, role: str) -> str:
        """Resolve a logical role to a provider/model string."""
        if role not in self.roles:
            raise ValueError(
                f"Role '{role}' not defined in provider config '{self.name}'. "
                f"Available roles: {list(self.roles)}"
            )
        return self.roles[role]


def _project_root() -> Path:
    """Find the project root (directory containing pyproject.toml)."""
    # Walk upward from this file: core/provider_config.py -> core -> agent_harness -> root
    current = Path(__file__).resolve().parent
    for ancestor in (current, *current.parents):
        if (ancestor / "pyproject.toml").exists():
            return ancestor
    raise FileNotFoundError(
        "Cannot locate project root (no pyproject.toml found in ancestors)"
    )


def load_provider_config(profile: str | None = None) -> ProviderConfig:
    """Load provider config from SIMULADORES_PROVIDER_PROFILE env var or argument.

    Args:
        profile: Explicit profile name. Falls back to the
                 SIMULADORES_PROVIDER_PROFILE env var, then "anthropic-vertex".
    """
    profile = profile or os.environ.get(
        "SIMULADORES_PROVIDER_PROFILE", "anthropic-vertex"
    )

    providers_dir = _project_root() / "config" / "providers"
    config_path = providers_dir / f"{profile}.toml"

    if not config_path.exists():
        available = sorted(p.stem for p in providers_dir.glob("*.toml"))
        raise FileNotFoundError(
            f"Provider profile '{profile}' not found. Available: {available}"
        )

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    return ProviderConfig(
        name=raw["provider"]["name"],
        gateway=GatewayType(raw["provider"]["gateway"]),
        base_url=raw["provider"].get("base_url"),
        roles=dict(raw["roles"]),
        auth_type=raw["auth"]["type"],
    )
