"""Tests for multi-domain routing and registry integration."""

import pytest

from agent_harness.gateway.router import (
    build_default_registry,
    route_operativo,
    RouteError,
)
from agent_harness.gateway.email_intake import (
    AttachmentRef,
    EmailIntakePayload,
    validate_email_payload,
    find_pdf_attachment,
)
from agent_harness.core.registry import OperativoRegistry
from agent_harness.core.operativo import OperativoStatus
from agent_harness.domains.dce.operativo import CPCOperativoInput
from agent_harness.domains.has.operativo import CEEOperativoInput
from agent_harness.domains.idp.operativo import IdpOperativoInput


class TestMultiDomainRegistry:
    def test_all_domains_registered(self):
        registry = build_default_registry()
        assert registry.domains == frozenset({"dce", "has", "idp"})

    def test_each_domain_routes(self):
        for domain in ["dce", "has", "idp"]:
            result = route_operativo(domain)
            assert result.domain == domain
            assert result.status == OperativoStatus.PENDING

    def test_domain_isolation_task_queues(self):
        registry = build_default_registry()
        queues = {
            registry.get(d).task_queue for d in registry.domains
        }
        assert len(queues) == 3  # All unique

    def test_domain_isolation_workflows(self):
        registry = build_default_registry()
        workflows = {
            registry.get(d).workflow_name for d in registry.domains
        }
        assert len(workflows) == 3  # All unique


class TestEmailToOperativoFlow:
    def _make_email_payload(self, classification):
        return EmailIntakePayload(
            email_id=f"email-{classification}",
            sender="test@example.com",
            subject=f"{classification.upper()} Review",
            classification=classification,
            attachments=[
                AttachmentRef(
                    filename="document.pdf",
                    storage_path=f"gs://bucket/{classification}/doc.pdf",
                    content_type="application/pdf",
                    size_bytes=1024,
                )
            ],
            received_at="2026-02-21T12:00:00Z",
        )

    def test_cpc_email_to_route(self):
        payload = self._make_email_payload("dce")
        validate_email_payload(payload)
        result = route_operativo(payload.classification)
        assert result.domain == "dce"
        assert result.workflow_name == "CPCWorkflow"

    def test_cee_email_to_route(self):
        payload = self._make_email_payload("has")
        validate_email_payload(payload)
        result = route_operativo(payload.classification)
        assert result.domain == "has"
        assert result.workflow_name == "CEEWorkflow"

    def test_idp_email_to_route(self):
        payload = self._make_email_payload("idp")
        validate_email_payload(payload)
        result = route_operativo(payload.classification)
        assert result.domain == "idp"
        assert result.workflow_name == "IdpWorkflow"

    def test_pdf_extraction_from_email(self):
        payload = self._make_email_payload("dce")
        pdf = find_pdf_attachment(payload)
        assert pdf is not None
        assert pdf.filename == "document.pdf"


class TestDomainInputTypes:
    def test_cpc_input_type(self):
        inp = CPCOperativoInput(
            pdf_path="/path.pdf", pdf_filename="test.pdf", caller_id="u1",
        )
        assert inp.pdf_path == "/path.pdf"

    def test_cee_input_type(self):
        inp = CEEOperativoInput(
            document_path="/path.pdf", document_filename="doc.pdf",
            caller_id="u1", document_type="attestation",
        )
        assert inp.document_type == "attestation"

    def test_idp_input_type(self):
        inp = IdpOperativoInput(
            document_path="/tmp/doc.pdf", plugin_id="invoices", caller_id="u1",
        )
        assert inp.document_path == "/tmp/doc.pdf"


class TestGatewayExports:
    def test_gateway_exports(self):
        from agent_harness.gateway import (
            DispatchResult,
            RouteResult,
            EmailIntakePayload,
            route_operativo,
            validate_email_payload,
        )
        assert DispatchResult is not None
        assert RouteResult is not None

    def test_domains_supported(self):
        from agent_harness.domains import SUPPORTED_DOMAINS
        assert SUPPORTED_DOMAINS == frozenset({"dce", "has", "idp"})
