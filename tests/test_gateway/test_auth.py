"""Tests for API key authentication."""

from __future__ import annotations

import pytest

from agent_harness.gateway.auth import ApiKeyAuth, AuthResult


class TestAuthResult:
    """AuthResult dataclass tests."""

    def test_frozen(self):
        result = AuthResult(authenticated=True, caller_id="x")
        with pytest.raises(AttributeError):
            result.authenticated = False  # type: ignore[misc]

    def test_defaults(self):
        result = AuthResult(authenticated=False)
        assert result.caller_id is None


class TestApiKeyAuth:
    """ApiKeyAuth class tests."""

    def test_disabled_returns_anonymous(self):
        auth = ApiKeyAuth(enabled=False)
        result = auth.authenticate(None)
        assert result.authenticated is True
        assert result.caller_id == "anonymous"

    def test_disabled_ignores_key(self):
        auth = ApiKeyAuth(keys={"k": "c"}, enabled=False)
        result = auth.authenticate("wrong")
        assert result.authenticated is True
        assert result.caller_id == "anonymous"

    def test_enabled_valid_key(self):
        auth = ApiKeyAuth(keys={"sk-abc": "acme"})
        result = auth.authenticate("sk-abc")
        assert result.authenticated is True
        assert result.caller_id == "acme"

    def test_enabled_invalid_key(self):
        auth = ApiKeyAuth(keys={"sk-abc": "acme"})
        result = auth.authenticate("sk-wrong")
        assert result.authenticated is False
        assert result.caller_id is None

    def test_enabled_missing_key(self):
        auth = ApiKeyAuth(keys={"sk-abc": "acme"})
        result = auth.authenticate(None)
        assert result.authenticated is False

    def test_enabled_empty_dict_rejects_all(self):
        auth = ApiKeyAuth(keys={}, enabled=True)
        result = auth.authenticate("anything")
        assert result.authenticated is False

    def test_multiple_keys(self):
        auth = ApiKeyAuth(keys={"k1": "c1", "k2": "c2"})
        assert auth.authenticate("k1").caller_id == "c1"
        assert auth.authenticate("k2").caller_id == "c2"
        assert auth.authenticate("k3").authenticated is False


class TestFromEnvString:
    """ApiKeyAuth.from_env_string() tests."""

    def test_empty_string_disables_auth(self):
        auth = ApiKeyAuth.from_env_string("")
        assert auth.enabled is False
        assert auth.authenticate(None).authenticated is True

    def test_whitespace_only_disables_auth(self):
        auth = ApiKeyAuth.from_env_string("   ")
        assert auth.enabled is False

    def test_single_pair(self):
        auth = ApiKeyAuth.from_env_string("sk-abc:acme")
        assert auth.enabled is True
        assert auth.authenticate("sk-abc").caller_id == "acme"

    def test_multiple_pairs(self):
        auth = ApiKeyAuth.from_env_string("k1:c1,k2:c2")
        assert auth.authenticate("k1").caller_id == "c1"
        assert auth.authenticate("k2").caller_id == "c2"

    def test_whitespace_handling(self):
        auth = ApiKeyAuth.from_env_string(" k1 : c1 , k2 : c2 ")
        assert auth.authenticate("k1").caller_id == "c1"
        assert auth.authenticate("k2").caller_id == "c2"

    def test_malformed_pairs_skipped(self):
        auth = ApiKeyAuth.from_env_string("k1:c1,badpair,k2:c2")
        assert auth.authenticate("k1").caller_id == "c1"
        assert auth.authenticate("k2").caller_id == "c2"
        assert auth.authenticate("badpair").authenticated is False

    def test_empty_key_or_caller_skipped(self):
        auth = ApiKeyAuth.from_env_string(":c1,k2:")
        assert auth.enabled is True
        # Both pairs have empty key or caller, so dict is empty
        assert auth.authenticate(":c1").authenticated is False
