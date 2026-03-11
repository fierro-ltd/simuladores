"""Test that e2e script helpers produce Excel alongside JSON."""

from __future__ import annotations

import tempfile
from pathlib import Path

from agent_harness.export.citation_matrix_excel import export_citation_matrix


def test_export_from_e2e_full_json():
    """Simulate what the e2e script does: load full.json, export Excel."""
    structured_result = {
        "operativo_id": "dce-e2e-test",
        "corrected_citation_matrix": [
            {
                "citation_text": "16 CFR Part 1303",
                "original_verdict": "PASS",
                "corrected_verdict": "VALID",
                "corrected_rationale": "Valid.",
                "correction_type": "confirmed",
            },
        ],
        "qa_summary": {"total_checks": 1, "blocking": 0, "warnings": 0, "info": 1},
    }

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dce-e2e-test_citation_matrix.xlsx"
        result = export_citation_matrix(
            structured_result=structured_result,
            pdf_filename="test.pdf",
            output_path=path,
        )
        assert result == path
        assert path.exists()
        assert path.stat().st_size > 0
