"""Santos planner agent — plans operativo execution with no tool calls.

Santos is the planning agent (Opus 4.6). During the PLAN phase it produces
a structured JSON execution plan. It never calls tools directly.
"""

from __future__ import annotations

import json
import logging
import re

from agent_harness.agents.base import AGENT_EFFORTS, AGENT_MODELS, BaseAgent, resolve_agent_model
from agent_harness.core.plan import AgentTask, ExecutionPlan
from agent_harness.llm.client import AnthropicClient

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)
_SINGLE_LINE_COMMENT_RE = re.compile(r"^\s*//[^\n]*", re.MULTILINE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


SANTOS_SYSTEM_IDENTITY = (
    "You are Santos, the planning agent for operativos. "
    "Your role is to analyse the incoming task and produce a structured "
    "execution plan as JSON. You have no tool access — you plan only, "
    "never execute. Each step in your plan must name the responsible agent, "
    "the action, and any required parameters."
)


def _default_cpc_plan(operativo_id: str) -> ExecutionPlan:
    """Return a default 6-step DCE plan as a safe fallback."""
    return ExecutionPlan(
        operativo_id=operativo_id,
        tasks=[
            AgentTask(agent="santos", action="plan", params={}),
            AgentTask(agent="medina", action="investigate", params={}),
            AgentTask(agent="gemini", action="vision_extract", params={}),
            AgentTask(agent="lamponne", action="execute", params={}),
            AgentTask(agent="santos", action="qa_review", params={}),
            AgentTask(agent="ravenna", action="synthesize", params={}),
        ],
    )


def _repair_json(text: str) -> str:
    """Attempt to repair common JSON quirks from LLM output.

    Handles:
    - Single-line ``//`` comments
    - Trailing commas before ``]`` or ``}``
    """
    text = _SINGLE_LINE_COMMENT_RE.sub("", text)
    text = _TRAILING_COMMA_RE.sub(r"\1", text)
    return text


def parse_plan_json(raw: str, operativo_id: str) -> ExecutionPlan:
    """Parse raw JSON from Santos into an ExecutionPlan.

    Expects ``{"steps": [{"agent": str, "action": str, "params": dict}, ...]}``

    The parser is resilient to common LLM output quirks:

    - Markdown code fences around the JSON
    - Surrounding prose (extracts first ``{`` to last ``}``)
    - Single-line ``//`` comments
    - Trailing commas before ``]`` or ``}``

    If all parsing attempts fail, returns a default 6-step DCE plan
    and logs a warning instead of crashing.
    """
    # Strip markdown code fences if present
    text = raw.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Extract JSON object from surrounding prose
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    # First attempt: parse as-is
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Second attempt: repair common quirks
    if data is None:
        try:
            data = json.loads(_repair_json(text))
        except json.JSONDecodeError:
            pass

    # Fallback: return default plan
    if data is None or not isinstance(data, dict):
        logger.warning(
            "Santos plan JSON unparseable for operativo %s — using default DCE plan. Raw: %.200s",
            operativo_id,
            raw,
        )
        return _default_cpc_plan(operativo_id)

    if "steps" not in data:
        logger.warning(
            "Santos plan JSON missing 'steps' key for operativo %s — using default DCE plan",
            operativo_id,
        )
        return _default_cpc_plan(operativo_id)

    tasks: list[AgentTask] = []
    for step in data["steps"]:
        tasks.append(
            AgentTask(
                agent=step.get("agent", "unknown"),
                action=step.get("action", "unknown"),
                params=step.get("params", {}),
            )
        )

    return ExecutionPlan(operativo_id=operativo_id, tasks=tasks)


class SantosPlanner:
    """Santos planning wrapper — no tools, plan-only.

    Wraps a BaseAgent to produce execution plans.
    """

    tools = None

    def __init__(self, base_agent: BaseAgent, provider=None) -> None:
        self.base_agent = base_agent
        self._provider = provider

    async def plan(
        self,
        client: AnthropicClient,
        operativo_id: str,
        input_description: str,
        domain_memory: str,
        session_state: str = "",
        semantic_patterns: list[str] | None = None,
    ) -> ExecutionPlan:
        """Produce a structured execution plan for an operativo.

        Calls the LLM (Opus) with a planning prompt and parses the JSON
        response into an :class:`ExecutionPlan`.

        Args:
            client: Anthropic API client.
            operativo_id: Unique identifier for this operativo.
            input_description: Human-readable description of the task.
            domain_memory: Domain memory content (DCE.md etc.).
            session_state: Optional session state from previous phases.
            semantic_patterns: Optional relevant patterns from semantic memory.

        Returns:
            Parsed ExecutionPlan with ordered agent tasks.

        Raises:
            ValueError: If the LLM response cannot be parsed as a valid plan.
        """
        user_message = (
            f"Create an execution plan for the following operativo.\n\n"
            f"Operativo ID: {operativo_id}\n"
            f"Task: {input_description}\n\n"
            f"Respond with a JSON object containing a 'steps' array. "
            f"Each step must have 'agent', 'action', and 'params' fields."
        )

        prompt = self.base_agent.build_prompt(
            user_message=user_message,
            domain_memory=domain_memory,
            semantic_patterns=semantic_patterns,
            session_state=session_state,
        )

        model = resolve_agent_model("santos", self._provider)

        result = await client.send_message(
            prompt=prompt,
            model=model,
            reasoning_effort=AGENT_EFFORTS["santos"],
        )

        return parse_plan_json(result.content, operativo_id)
