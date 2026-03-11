"""Ravenna — the Synthesizer agent. Sonnet-tier."""

from __future__ import annotations

from agent_harness.agents.base import AGENT_EFFORTS, AgentConfig, BaseAgent, AGENT_MODELS, resolve_agent_model
from agent_harness.llm.client import AnthropicClient
from agent_harness.llm.tool_handler import ToolHandler

RAVENNA_SYSTEM_IDENTITY = """You are Ravenna, the Synthesizer of the Agent Harness.

Your role is to read all PROGRESS.md field reports from Phases 1-4,
load raw_output.json and qa_report.json, and assemble the final
structured_result.json with QA summary.

## Synthesis Rules
- Read ALL PROGRESS.md entries (Phases 1-4 field reports)
- Load raw_output.json (Phase 3 execution results)
- Load qa_report.json (Phase 4 QA review results)
- Assemble structured_result.json with all fields + QA summary
- Permission-gated delivery: check caller permissions before releasing
- Write PROGRESS.md Phase 5 field report

## Output Structure
structured_result.json must contain:
- operativo_id, status, domain
- result: extraction, validation, navigation, corrections
- qa_summary: total_checks, blocking, warnings, info, corrections_applied
- report_url: path to generated report
- metadata: duration_seconds, phases_completed, agents_invoked

## Quality Standards
- Never omit QA summary even if no issues were found
- Always include metadata with timing and agent tracking
- Report must be complete before delivery
"""

RAVENNA_TOOLS: list[dict] = [
    {
        "name": "read_progress",
        "description": "Read PROGRESS.md field reports for all phases.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operativo_id": {"type": "string", "description": "Operativo ID"},
            },
            "required": ["operativo_id"],
        },
    },
    {
        "name": "load_artifact",
        "description": "Load a JSON artifact (raw_output.json, qa_report.json, input_snapshot.json).",
        "input_schema": {
            "type": "object",
            "properties": {
                "operativo_id": {"type": "string", "description": "Operativo ID"},
                "artifact_name": {"type": "string", "description": "Artifact filename"},
            },
            "required": ["operativo_id", "artifact_name"],
        },
    },
    {
        "name": "write_structured_result",
        "description": "Write the final structured_result.json.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operativo_id": {"type": "string", "description": "Operativo ID"},
                "result_json": {"type": "string", "description": "JSON string of the result"},
            },
            "required": ["operativo_id", "result_json"],
        },
    },
    {
        "name": "check_caller_permission",
        "description": "Check if the caller has permission to receive the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caller_id": {"type": "string", "description": "Caller identifier"},
                "operativo_id": {"type": "string", "description": "Operativo ID"},
            },
            "required": ["caller_id", "operativo_id"],
        },
    },
]


class RavennaSynthesizer:
    """Ravenna synthesis wrapper — assembles final structured result.

    Uses Sonnet model. Reads progress reports, loads artifacts, checks
    permissions, and writes the final structured_result.json.
    """

    def __init__(self, domain: str, provider=None) -> None:
        self.config = AgentConfig(
            name="ravenna",
            model=resolve_agent_model("ravenna", provider),
            system_identity=RAVENNA_SYSTEM_IDENTITY,
            domain=domain,
            reasoning_effort=AGENT_EFFORTS["ravenna"],
        )
        self._agent = BaseAgent(self.config)

    async def synthesize(
        self,
        client: AnthropicClient,
        tool_handler: ToolHandler,
        operativo_id: str,
        progress: str,
        raw_output_json: str,
        qa_report_json: str,
        caller_id: str,
        domain_memory: str,
        semantic_patterns: list[str] | None = None,
    ) -> str:
        """Synthesize the final result from all phase outputs.

        Args:
            client: Anthropic API client.
            tool_handler: Tool handler with registered tool implementations.
            operativo_id: Operativo identifier.
            progress: PROGRESS.md content from Phases 1-4.
            raw_output_json: Raw output JSON from Phase 3 execution.
            qa_report_json: QA report JSON from Phase 4 review.
            caller_id: Caller identifier for permission check.
            domain_memory: Domain memory content.
            semantic_patterns: Optional patterns from semantic memory for L3.

        Returns:
            Final content string from the tool loop (structured result).
        """
        user_message = (
            f"Synthesize the final result for operativo {operativo_id}.\n\n"
            f"## Progress Reports\n{progress}\n\n"
            f"## Raw Output\n{raw_output_json}\n\n"
            f"## QA Report\n{qa_report_json}\n\n"
            f"Caller ID for permission check: {caller_id}\n\n"
            f"1. Read all progress reports using read_progress\n"
            f"2. Load raw_output.json and qa_report.json using load_artifact\n"
            f"3. Check caller permission using check_caller_permission\n"
            f"4. Assemble and write structured_result.json using write_structured_result"
        )

        prompt = self._agent.build_prompt(
            user_message=user_message,
            domain_memory=domain_memory,
            semantic_patterns=semantic_patterns,
        )

        result = await tool_handler.run_loop(
            prompt=prompt,
            model=self.config.model,
            tools=RAVENNA_TOOLS,
            max_turns=self.config.max_turns,
            reasoning_effort=self.config.reasoning_effort,
        )

        return result.final_content
