"""Domain registry: discovers and loads domain manifests from domain.toml files."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DomainManifest:
    """Immutable manifest describing a single domain's configuration."""

    id: str
    name: str
    version: str
    mcp_server_module: str
    mcp_server_port: int
    temporal_task_queue: str
    workflow_id_prefix: str
    memory_collection: str
    models: dict[str, str]
    injection_guard: dict
    limits: dict


class DomainRegistry:
    """Discovers and loads domain manifests from domain.toml files.

    Scans ``domains_root`` for subdirectories containing a ``domain.toml``
    file and materialises each into a :class:`DomainManifest`.
    """

    def __init__(self, domains_root: Path) -> None:
        self._manifests: dict[str, DomainManifest] = {}
        self._load_all(domains_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, domain_id: str) -> DomainManifest:
        """Return the manifest for *domain_id*. Raises ValueError if unknown."""
        if domain_id not in self._manifests:
            raise ValueError(f"Unknown domain: '{domain_id}'")
        return self._manifests[domain_id]

    def list_domains(self) -> list[str]:
        """Return all loaded domain IDs."""
        return list(self._manifests.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self, domains_root: Path) -> None:
        if not domains_root.is_dir():
            return
        for toml_path in sorted(domains_root.glob("*/domain.toml")):
            manifest = self._parse_toml(toml_path)
            self._manifests[manifest.id] = manifest

    @staticmethod
    def _parse_toml(path: Path) -> DomainManifest:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        d = data["domain"]
        return DomainManifest(
            id=d["id"],
            name=d["name"],
            version=d["version"],
            mcp_server_module=d["mcp"]["server_module"],
            mcp_server_port=d["mcp"]["server_port"],
            temporal_task_queue=d["temporal"]["task_queue"],
            workflow_id_prefix=d["temporal"]["workflow_id_prefix"],
            memory_collection=d["memory"]["collection"],
            models=dict(d["models"]),
            injection_guard=dict(d["injection_guard"]),
            limits=dict(d["limits"]),
        )
