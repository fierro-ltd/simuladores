"""Tests for DCE citation registry and completeness checker."""


from agent_harness.domains.dce import (
    CPC_CITATION_REGISTRY,
    CitationRule,
    CitationType,
    build_completeness_report,
    classify_citations,
    normalize_citation,
    required_citations,
)


class Test1252ExistsButNonCitable:
    """16 CFR Part 1252 exists but is not DCE citable."""

    def test_1252_normalizes_to_canonical(self):
        assert normalize_citation("16 CFR Part 1252") == "16 CFR Part 1252"
        assert normalize_citation("16 CFR 1252") == "16 CFR Part 1252"

    def test_1252_classified_as_non_citable(self):
        covered, invalid, non_citable = classify_citations(["16 CFR Part 1252"])
        assert covered == []
        assert invalid == []
        assert len(non_citable) == 1
        assert "1252" in non_citable[0][0]
        assert "exemption" in non_citable[0][1].lower() or "certifiable" in non_citable[0][1].lower()


class Test1107ProceduralNonCitable:
    """16 CFR 1107.21 is procedural, not DCE citable."""

    def test_1107_21_normalizes(self):
        assert normalize_citation("16 CFR 1107.21") == "16 CFR 1107.21"
        assert normalize_citation("16 CFR § 1107.21") == "16 CFR 1107.21"

    def test_1107_21_classified_as_non_citable(self):
        covered, invalid, non_citable = classify_citations(["16 CFR 1107.21"])
        assert covered == []
        assert invalid == []
        assert len(non_citable) == 1
        assert "1107" in non_citable[0][0]
        assert "procedural" in non_citable[0][1].lower() or "operational" in non_citable[0][1].lower()


class TestSubsectionNormalization:
    """16 CFR 1303.2 and 16 CFR 1261.2 are definition subsections, not standalone citable."""

    def test_1303_2_normalizes_and_classified_non_citable(self):
        assert normalize_citation("16 CFR 1303.2") == "16 CFR 1303.2"
        covered, invalid, non_citable = classify_citations(["16 CFR 1303.2"])
        assert covered == []
        assert len(non_citable) == 1
        assert "1303.2" in non_citable[0][0]
        assert "subsection" in non_citable[0][1].lower() or "definition" in non_citable[0][1].lower()

    def test_1261_2_normalizes_and_classified_non_citable(self):
        assert normalize_citation("16 CFR 1261.2") == "16 CFR 1261.2"
        covered, invalid, non_citable = classify_citations(["16 CFR 1261.2"])
        assert covered == []
        assert len(non_citable) == 1
        assert "1261.2" in non_citable[0][0]


class TestMissing1501ForUnder3Profile:
    """16 CFR Part 1501 required for products with age_months < 36."""

    def test_under_3_requires_1501(self):
        profile = {"age_months": 24}
        req = required_citations(profile)
        assert "16 CFR Part 1501" in req

    def test_over_3_does_not_require_1501(self):
        profile = {"age_months": 48}
        req = required_citations(profile)
        assert "16 CFR Part 1501" not in req

    def test_exactly_36_does_not_require_1501(self):
        profile = {"age_months": 36}
        req = required_citations(profile)
        assert "16 CFR Part 1501" not in req

    def test_missing_1501_reported_in_completeness(self):
        profile = {"age_months": 24}
        provided = ["16 CFR Part 1261", "16 CFR Part 1303", "15 U.S.C. 1278a"]
        report = build_completeness_report(profile, provided)
        assert "16 CFR Part 1501" in report.missing
        assert report.is_complete is False

    def test_complete_when_1501_provided_for_under_3(self):
        profile = {"age_months": 24}
        provided = [
            "16 CFR Part 1261",
            "16 CFR Part 1303",
            "15 U.S.C. 1278a",
            "16 CFR Part 1501",
        ]
        report = build_completeness_report(profile, provided)
        assert "16 CFR Part 1501" not in report.missing
        assert report.is_complete is True


class TestCPSIASectionAliasToCanonical:
    """compliance Section references alias to canonical statutory form."""

    def test_cpsia_sec101_to_15_usc_1278a(self):
        assert normalize_citation("compliance Sec101") == "15 U.S.C. 1278a"
        assert normalize_citation("compliance Section 101") == "15 U.S.C. 1278a"
        assert normalize_citation("compliance Sec 101") == "15 U.S.C. 1278a"

    def test_cpsia_sec108_to_16_cfr_1307(self):
        assert normalize_citation("compliance Sec108") == "16 CFR Part 1307"
        assert normalize_citation("compliance Section 108") == "16 CFR Part 1307"

    def test_cpsia_aliases_classified_as_covered_when_provided(self):
        covered, invalid, non_citable = classify_citations(
            ["compliance Section 101", "compliance Section 108"]
        )
        assert "15 U.S.C. 1278a" in covered
        assert "16 CFR Part 1307" in covered


class TestInvalidAndAliasHandling:
    """SOR, 40 CFR, ASTM F963, ASTM F2057 alias/invalid behavior."""

    def test_sor_invalid(self):
        assert normalize_citation("SOR-2018-83") is None
        assert normalize_citation("SOR-2021-148") is None
        covered, invalid, _ = classify_citations(["SOR-2018-83"])
        assert covered == []
        assert len(invalid) == 1
        assert "Canadian" in invalid[0][1] or "SOR" in invalid[0][0]

    def test_40_cfr_part_770_invalid(self):
        assert normalize_citation("40 CFR Part 770") is None
        covered, invalid, _ = classify_citations(["40 CFR Part 770"])
        assert covered == []
        assert len(invalid) == 1

    def test_astm_f963_invalid_or_alias(self):
        assert normalize_citation("ASTM F963-23") is None
        assert normalize_citation("ASTM F963") is None
        covered, invalid, _ = classify_citations(["ASTM F963-23"])
        assert covered == []
        assert len(invalid) == 1

    def test_astm_f2057_aliases_to_1261(self):
        assert normalize_citation("ASTM F2057-23") == "16 CFR Part 1261"
        assert normalize_citation("ASTM F2057") == "16 CFR Part 1261"
        covered, _, _ = classify_citations(["ASTM F2057-23"])
        assert "16 CFR Part 1261" in covered


class TestCitationRegistry:
    """Registry structure and CitationRule."""

    def test_registry_has_expected_entries(self):
        expected = [
            "16 CFR Part 1261",
            "16 CFR Part 1303",
            "15 U.S.C. 1278a",
            "16 CFR Part 1501",
            "16 CFR Part 1307",
            "16 CFR Part 1252",
            "16 CFR 1107.21",
            "16 CFR 1303.2",
            "16 CFR 1261.2",
        ]
        for e in expected:
            assert e in CPC_CITATION_REGISTRY, f"Missing: {e}"

    def test_citation_rule_has_citable_type(self):
        rule = CPC_CITATION_REGISTRY["16 CFR Part 1261"]
        assert isinstance(rule, CitationRule)
        assert rule.citable_type == CitationType.SUBSTANTIVE

    def test_1501_has_condition(self):
        rule = CPC_CITATION_REGISTRY["16 CFR Part 1501"]
        assert rule.condition == "age_months<36"

    def test_1307_has_condition(self):
        rule = CPC_CITATION_REGISTRY["16 CFR Part 1307"]
        assert rule.condition == "toy_or_childcare"


class TestRequiredCitations:
    """required_citations from product profile."""

    def test_universal_citations_always_required(self):
        profile = {}
        req = required_citations(profile)
        assert "16 CFR Part 1303" in req
        assert "15 U.S.C. 1278a" in req

    def test_1261_required_for_dresser_category(self):
        profile = {"product_category": "dresser"}
        req = required_citations(profile)
        assert "16 CFR Part 1261" in req

    def test_toy_adds_1307(self):
        profile = {"is_toy": True}
        req = required_citations(profile)
        assert "16 CFR Part 1307" in req

    def test_childcare_adds_1307(self):
        profile = {"is_childcare": True}
        req = required_citations(profile)
        assert "16 CFR Part 1307" in req


class TestBuildCompletenessReport:
    """build_completeness_report behavior."""

    def test_report_structure(self):
        profile = {"age_months": 36}
        report = build_completeness_report(
            profile,
            ["16 CFR Part 1261", "16 CFR Part 1303", "15 U.S.C. 1278a", "SOR-2018-83"],
        )
        assert hasattr(report, "missing")
        assert hasattr(report, "invalid")
        assert hasattr(report, "non_citable_references")
        assert hasattr(report, "covered")
        assert hasattr(report, "required")
        assert hasattr(report, "is_complete")

    def test_invalid_in_report(self):
        profile = {}
        report = build_completeness_report(profile, ["40 CFR Part 770"])
        assert len(report.invalid) == 1
        assert "40 CFR" in report.invalid[0][0]

    def test_non_citable_in_report(self):
        profile = {}
        report = build_completeness_report(
            profile,
            ["16 CFR Part 1261", "16 CFR Part 1252", "16 CFR 1107.21"],
        )
        assert "16 CFR Part 1261" in report.covered
        assert len(report.non_citable_references) >= 2  # 1252 and 1107.21
