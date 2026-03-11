"""Lamponne: the Executor agent for the DCE domain."""

from __future__ import annotations

from agent_harness.agents.base import AGENT_EFFORTS, AgentConfig, BaseAgent, AGENT_MODELS, resolve_agent_model
from agent_harness.llm.client import AnthropicClient
from agent_harness.llm.tool_handler import ToolHandler

LAMPONNE_SYSTEM_IDENTITY: str = (
    "You are Lamponne, the Executor agent. Your role is to carry out tool "
    "invocations requested by the planner. You have two tools at your disposal: "
    "discover_api (to explore the available DCE API operations) and execute_api "
    "(to invoke a specific operation with parameters). Always confirm the "
    "operation exists via discover_api before calling execute_api."
)

LAMPONNE_TOOLS: list[dict] = [
    {
        "name": "discover_api",
        "description": "Explore available DCE API operations, optionally filtered by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter operations by category.",
                    "enum": [
                        "extraction",
                        "navigation",
                        "validation",
                        "tools",
                        "global",
                    ],
                },
            },
            "required": [],
        },
    },
    {
        "name": "execute_api",
        "description": "Execute a DCE API operation with the given parameters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "The name of the DCE operation to execute.",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters to pass to the operation.",
                },
            },
            "required": ["operation", "params"],
        },
    },
]


class LamponneExecutor:
    """Lamponne execution wrapper — runs DCE API operations via tool loop.

    Uses Sonnet model. Discovers and executes DCE API operations
    according to the plan provided by Santos.
    """

    def __init__(self, domain: str, max_turns: int = 10, provider=None) -> None:
        self.config = AgentConfig(
            name="lamponne",
            model=resolve_agent_model("lamponne", provider),
            system_identity=LAMPONNE_SYSTEM_IDENTITY,
            domain=domain,
            max_turns=max_turns,
            reasoning_effort=AGENT_EFFORTS["lamponne"],
        )
        self._agent = BaseAgent(self.config)

    async def execute(
        self,
        client: AnthropicClient,
        tool_handler: ToolHandler,
        operativo_id: str,
        plan_json: str,
        domain_memory: str,
        session_state: str = "",
        semantic_patterns: list[str] | None = None,
    ) -> str:
        """Execute a plan by running DCE API operations via the tool loop.

        Args:
            client: Anthropic API client.
            tool_handler: Tool handler with registered tool implementations.
            operativo_id: Operativo identifier.
            plan_json: JSON execution plan from Santos.
            domain_memory: Domain memory content.
            session_state: Optional session state from prior phases.
            semantic_patterns: Optional patterns from semantic memory for L3.

        Returns:
            Final content string from the tool loop (execution results).
        """
        user_message = (
            f"Execute the following plan for operativo {operativo_id}.\n\n"
            f"Plan:\n{plan_json}\n\n"
            f"Use discover_api to verify each operation exists, then execute_api "
            f"to run it. Report results for each step."
        )

        prompt = self._agent.build_prompt(
            user_message=user_message,
            domain_memory=domain_memory,
            semantic_patterns=semantic_patterns,
            session_state=session_state,
        )

        result = await tool_handler.run_loop(
            prompt=prompt,
            model=self.config.model,
            tools=LAMPONNE_TOOLS,
            max_turns=self.config.max_turns,
            reasoning_effort=self.config.reasoning_effort,
        )

        return result.final_content
