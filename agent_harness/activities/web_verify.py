"""DCE web verification Temporal activity types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WebVerifyInput:
    """Input for DCE web verification activity."""

    operativo_id: str
    domain: str
    citation_completeness_report_json: str
    max_queries: int = 4


@dataclass(frozen=True)
class WebVerifyOutput:
    """Output from DCE web verification activity."""

    operativo_id: str
    verification_json: str
    phase_result: str
