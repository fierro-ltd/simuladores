"""API key authentication for the gateway.

Supports a simple key-to-caller mapping loaded from an environment
variable string.  When disabled, all requests pass as ``anonymous``.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthResult:
    """Result of an authentication attempt."""

    authenticated: bool
    caller_id: str | None = None


class ApiKeyAuth:
    """Simple API-key authenticator.

    Parameters
    ----------
    keys:
        Mapping of API key -> caller_id.
    enabled:
        When ``False``, authentication is bypassed and all requests
        are treated as ``anonymous``.
    """

    def __init__(self, keys: dict[str, str] | None = None, *, enabled: bool = True) -> None:
        self._keys: dict[str, str] = dict(keys) if keys else {}
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def authenticate(self, api_key: str | None) -> AuthResult:
        """Check an API key and return an ``AuthResult``.

        When disabled, returns authenticated=True with caller_id="anonymous".
        When enabled and the key is missing or invalid, returns authenticated=False.
        """
        if not self._enabled:
            return AuthResult(authenticated=True, caller_id="anonymous")

        if api_key is None:
            return AuthResult(authenticated=False)

        for stored_key, caller_id in self._keys.items():
            if hmac.compare_digest(api_key, stored_key):
                return AuthResult(authenticated=True, caller_id=caller_id)

        return AuthResult(authenticated=False)

    @classmethod
    def from_env_string(cls, env_value: str) -> "ApiKeyAuth":
        """Build from a comma-separated ``key:caller`` string.

        Example: ``"sk-abc123:acme,sk-xyz789:globex"``

        If the string is empty, returns a *disabled* instance (dev mode).
        """
        env_value = env_value.strip()
        if not env_value:
            return cls(enabled=False)

        keys: dict[str, str] = {}
        for pair in env_value.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if ":" not in pair:
                continue
            key, caller = pair.split(":", 1)
            key = key.strip()
            caller = caller.strip()
            if key and caller:
                keys[key] = caller

        return cls(keys=keys, enabled=True)
