"""Tests for sandbox interface and routing."""


from agent_harness.sandbox.python_runner import (
    SandboxRequest,
    SandboxResult,
    SandboxRouter,
)


class TestSandboxRequest:
    def test_default_request(self):
        req = SandboxRequest(code="x = 1 + 2", input_data={"a": 1})
        assert req.timeout_seconds == 10
        assert "re" in req.allowed_imports
        assert "json" in req.allowed_imports
        assert not req.requires_json

    def test_requires_json_flag(self):
        req = SandboxRequest(
            code="import json; json.loads('{}')",
            input_data={},
            requires_json=True,
        )
        assert req.requires_json


class TestSandboxResult:
    def test_success_result(self):
        result = SandboxResult(
            output="3", stdout="", error=None, execution_ms=5.2, backend="docker"
        )
        assert result.error is None
        assert result.backend == "docker"

    def test_error_result(self):
        result = SandboxResult(
            output="", stdout="", error="NameError: name 'x' is not defined",
            execution_ms=1.0, backend="docker"
        )
        assert result.error is not None

    def test_succeeded_property(self):
        success = SandboxResult(output="ok", stdout="", error=None, execution_ms=1.0, backend="docker")
        failure = SandboxResult(output="", stdout="", error="fail", execution_ms=1.0, backend="docker")
        assert success.succeeded
        assert not failure.succeeded


class TestSandboxRouter:
    def test_default_backend_is_docker(self):
        router = SandboxRouter()
        assert router.active_backend == "docker"

    def test_monty_not_available(self):
        router = SandboxRouter()
        assert not router.monty_available
