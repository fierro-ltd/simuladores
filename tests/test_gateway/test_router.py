"""Tests for domain router."""

import pytest

from agent_harness.gateway.router import (
    RouteResult,
    RouteError,
    build_default_registry,
    route_operativo,
)
from agent_harness.core.operativo import OperativoStatus
from agent_harness.core.registry import OperativoRegistry


class TestBuildDefaultRegistry:
    def test_has_three_domains(self):
        registry = build_default_registry()
        assert registry.domains == frozenset({"dce", "has", "idp"})

    def test_cpc_task_queue(self):
        registry = build_default_registry()
        assert registry.get("dce").task_queue == "dce-operativo"

    def test_cee_task_queue(self):
        registry = build_default_registry()
        assert registry.get("has").task_queue == "has-operativo"

    def test_idp_task_queue(self):
        registry = build_default_registry()
        assert registry.get("idp").task_queue == "nav-operativo"


class TestRouteOperativo:
    def test_route_cpc(self):
        result = route_operativo("dce")
        assert isinstance(result, RouteResult)
        assert result.domain == "dce"
        assert result.task_queue == "dce-operativo"
        assert result.workflow_name == "CPCWorkflow"
        assert result.status == OperativoStatus.PENDING
        assert result.operativo_id.startswith("dce-")

    def test_route_cee(self):
        result = route_operativo("has")
        assert result.domain == "has"
        assert result.operativo_id.startswith("has-")

    def test_route_navigator(self):
        result = route_operativo("idp")
        assert result.domain == "idp"
        assert result.operativo_id.startswith("idp-")

    def test_unknown_domain(self):
        with pytest.raises(RouteError, match="Unknown domain"):
            route_operativo("unknown")

    def test_empty_domain(self):
        with pytest.raises(RouteError, match="required"):
            route_operativo("")

    def test_custom_registry(self):
        reg = OperativoRegistry()
        reg.register("custom", "custom-queue", "CustomWorkflow")
        result = route_operativo("custom", registry=reg)
        assert result.domain == "custom"
        assert result.task_queue == "custom-queue"

    def test_unique_ids(self):
        ids = {route_operativo("dce").operativo_id for _ in range(10)}
        assert len(ids) == 10
