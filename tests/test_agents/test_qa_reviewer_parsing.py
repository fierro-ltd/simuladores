"""Tests for QA output parsing with citation classification categories."""

from agent_harness.agents.qa_reviewer import _parse_qa_json


class TestParseQAJsonCitationClassification:
    """Tests for citation_classification in QA output parsing."""

    def test_parses_citation_classification(self):
        raw = """{
            "checks": [
                {
                    "field": "citations",
                    "expected": "16 CFR Part 1307",
                    "actual": "",
                    "severity": "BLOCKING",
                    "auto_correctable": false,
                    "citation_classification": "MISSING_CPC_CITATION"
                }
            ],
            "corrected_citation_matrix": []
        }"""
        report = _parse_qa_json(raw, "op-1")
        assert len(report.checks) == 1
        assert report.checks[0].citation_classification == "MISSING_CPC_CITATION"

    def test_parses_all_four_classifications(self):
        raw = """{
            "checks": [
                {"field": "a", "expected": "x", "actual": "y", "severity": "BLOCKING", "auto_correctable": false, "citation_classification": "MISSING_CPC_CITATION"},
                {"field": "b", "expected": "x", "actual": "y", "severity": "WARNING", "auto_correctable": false, "citation_classification": "INVALID_CPC_CITATION"},
                {"field": "c", "expected": "x", "actual": "y", "severity": "INFO", "auto_correctable": false, "citation_classification": "NON_CPC_OPERATIONAL_REQUIREMENT"},
                {"field": "d", "expected": "x", "actual": "y", "severity": "WARNING", "auto_correctable": false, "citation_classification": "AMBIGUOUS_REQUIRES_REVIEW"}
            ],
            "corrected_citation_matrix": []
        }"""
        report = _parse_qa_json(raw, "op-1")
        assert report.checks[0].citation_classification == "MISSING_CPC_CITATION"
        assert report.checks[1].citation_classification == "INVALID_CPC_CITATION"
        assert report.checks[2].citation_classification == "NON_CPC_OPERATIONAL_REQUIREMENT"
        assert report.checks[3].citation_classification == "AMBIGUOUS_REQUIRES_REVIEW"

    def test_ignores_invalid_classification(self):
        raw = """{
            "checks": [
                {
                    "field": "citations",
                    "expected": "x",
                    "actual": "y",
                    "severity": "BLOCKING",
                    "auto_correctable": false,
                    "citation_classification": "INVALID_CATEGORY"
                }
            ],
            "corrected_citation_matrix": []
        }"""
        report = _parse_qa_json(raw, "op-1")
        assert report.checks[0].citation_classification is None

    def test_backward_compat_no_citation_classification(self):
        raw = """{
            "checks": [
                {"field": "product", "expected": "A", "actual": "B", "severity": "INFO", "auto_correctable": false}
            ],
            "corrected_citation_matrix": []
        }"""
        report = _parse_qa_json(raw, "op-1")
        assert report.checks[0].citation_classification is None
