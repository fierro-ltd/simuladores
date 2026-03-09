"""Operativo registry: maps domains to task queues and workflows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegistryEntry:
    """A registered domain with its task queue and workflow."""

    domain: str
    task_queue: str
    workflow_name: str


class OperativoRegistry:
    """Registry of domain -> task queue/workflow mappings."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(self, domain: str, task_queue: str, workflow_name: str) -> None:
        """Register a domain. Raises ValueError on duplicate."""
        if domain in self._entries:
            raise ValueError(f"Domain '{domain}' is already registered")
        self._entries[domain] = RegistryEntry(
            domain=domain, task_queue=task_queue, workflow_name=workflow_name
        )

    def get(self, domain: str) -> RegistryEntry:
        """Get a registry entry. Raises KeyError if not found."""
        if domain not in self._entries:
            raise KeyError(f"Domain '{domain}' is not registered")
        return self._entries[domain]

    @property
    def domains(self) -> frozenset[str]:
        """All registered domain names."""
        return frozenset(self._entries.keys())
