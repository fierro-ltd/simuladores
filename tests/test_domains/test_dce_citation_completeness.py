"""Tests for DCE citation completeness registry helpers."""

import json
import pytest

from agent_harness.domains.dce.citation_completeness import (
    derive_provided_citations,
    derive_product_profile,
    compute_completeness_report,
)


class TestDeriveProvidedCitations:
    """Tests for derive_provided_citations."""

    def test_from_structured_fields_regulations(self):
        data = {
            "structured_fields": {
                "regulations": ["16 CFR Part 1303", "ASTM F963", "16 CFR Part 1307"],
            },
        }
        assert derive_provided_citations(data) == [
            "16 CFR Part 1303",
            "ASTM F963",
            "16 CFR Part 1307",
        ]

    def test_from_citations_key(self):
        data = {"Citations": ["16 CFR Part 1261", "ASTM F2057"]}
        assert derive_provided_citations(data) == ["16 CFR Part 1261", "ASTM F2057"]

    def test_from_semicolon_separated_string(self):
        data = {"structured_fields": {"regulations": "16 CFR Part 1303; ASTM F963"}}
        assert derive_provided_citations(data) == ["16 CFR Part 1303", "ASTM F963"]

    def test_deduplicates(self):
        data = {"structured_fields": {"regulations": ["16 CFR Part 1303", "16 CFR Part 1303"]}}
        assert derive_provided_citations(data) == ["16 CFR Part 1303"]

    def test_empty_extraction(self):
        assert derive_provided_citations({}) == []
        assert derive_provided_citations({"structured_fields": {}}) == []


class TestDeriveProductProfile:
    """Tests for derive_product_profile."""

    def test_from_structured_fields(self):
        data = {
            "structured_fields": {
                "product_description": "Toy car",
                "brand_name": "Acme",
                "place_of_manufacture": "China",
            },
        }
        profile = derive_product_profile(data)
        assert profile["product_description"] == "Toy car"
        assert profile["brand_name"] == "Acme"
        assert profile["place_of_manufacture"] == "China"

    def test_fallback_product_keys(self):
        data = {"product_name": "Widget", "brand_name": "BrandX"}
        profile = derive_product_profile(data)
        assert profile["product_description"] == "Widget"
        assert profile["brand_name"] == "BrandX"


class TestComputeCompletenessReport:
    """Tests for compute_completeness_report and web_verification_recommended."""

    def test_report_shape(self):
        snapshot = json.dumps({
            "structured_fields": {
                "regulations": ["16 CFR Part 1303", "ASTM F963"],
                "product_description": "Children's toy",
            },
        })
        report_str = compute_completeness_report(snapshot)
        report = json.loads(report_str)
        assert "provided_citations" in report
        assert "product_profile" in report
        assert "citation_classifications" in report
        assert "unknown_count" in report
        assert "web_verification_recommended" in report

    def test_known_citations_no_ambiguity(self):
        snapshot = json.dumps({
            "structured_fields": {
                "regulations": ["16 CFR Part 1261", "16 CFR Part 1303", "15 U.S.C. 1278a"],
                "product_description": "Plush toy",
            },
        })
        report = json.loads(compute_completeness_report(snapshot))
        assert report["unknown_count"] == 0
        assert report["web_verification_recommended"] is False

    def test_unknown_citation_sets_web_verification(self):
        snapshot = json.dumps({
            "structured_fields": {
                "regulations": ["SOR-2018-83", "16 CFR Part 1303"],  # SOR is Canadian, unknown
                "product_description": "Dresser for children",
            },
        })
        report = json.loads(compute_completeness_report(snapshot))
        assert report["unknown_count"] >= 1
        assert report["web_verification_recommended"] is True

    def test_scope_uncertainty_no_product_description(self):
        snapshot = json.dumps({
            "structured_fields": {
                "regulations": ["16 CFR Part 1303"],
                "product_description": "",
            },
        })
        report = json.loads(compute_completeness_report(snapshot))
        assert report["web_verification_recommended"] is True

    def test_empty_snapshot_graceful(self):
        report_str = compute_completeness_report("{}")
        report = json.loads(report_str)
        assert report["provided_citations"] == []
        assert report["unknown_count"] == 0
        assert report["web_verification_recommended"] is True  # scope uncertainty
