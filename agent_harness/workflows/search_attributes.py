"""Temporal search attributes for operativo workflows.

Custom search attributes enable filtering and querying workflows
in the Temporal UI and via the Temporal API.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SearchAttributeType(StrEnum):
    KEYWORD = "Keyword"
    TEXT = "Text"
    INT = "Int"
    DOUBLE = "Double"
    BOOL = "Bool"
    DATETIME = "Datetime"


@dataclass(frozen=True)
class SearchAttribute:
    """Definition of a Temporal search attribute."""
    name: str
    attribute_type: SearchAttributeType
    description: str


# Standard search attributes for all operativo workflows
OPERATIVO_SEARCH_ATTRIBUTES: list[SearchAttribute] = [
    SearchAttribute(
        name="OperativoDomain",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Domain of the operativo (dce, has, idp)",
    ),
    SearchAttribute(
        name="OperativoId",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Unique operativo identifier",
    ),
    SearchAttribute(
        name="OperativoStatus",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Current status (PENDING, RUNNING, COMPLETED, FAILED, NEEDS_REVIEW)",
    ),
    SearchAttribute(
        name="CurrentPhase",
        attribute_type=SearchAttributeType.INT,
        description="Current phase number (0-6)",
    ),
    SearchAttribute(
        name="CallerID",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Caller identifier for the operativo",
    ),
    SearchAttribute(
        name="HasBlockingIssues",
        attribute_type=SearchAttributeType.BOOL,
        description="Whether the operativo has unresolved blocking QA issues",
    ),
]


def build_search_attributes(
    operativo_id: str,
    domain: str,
    status: str = "PENDING",
    current_phase: int = 0,
    caller_id: str = "",
    has_blocking: bool = False,
) -> dict[str, str | int | bool]:
    """Build search attribute values for a workflow."""
    attrs: dict[str, str | int | bool] = {
        "OperativoId": operativo_id,
        "OperativoDomain": domain,
        "OperativoStatus": status,
        "CurrentPhase": current_phase,
    }
    if caller_id:
        attrs["CallerID"] = caller_id
    attrs["HasBlockingIssues"] = has_blocking
    return attrs
