"""Tool-use loop handler for multi-turn Claude tool interactions.

Manages the send-execute-respond cycle when Claude uses tools,
accumulating usage and tracking errors across turns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from agent_harness.llm.client import AnthropicClient, MessageResult, TokenUsage, ToolCall
from agent_harness.llm.loop_detection import ResourceEditTracker
from agent_harness.prompt.compaction_client import CompactionClient

# Type alias for tool handler functions
ToolHandlerFunc = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True)
class ToolLoopResult:
    """Result of a complete tool-use loop."""

    final_content: str
    turns: int
    tool_calls_made: list[ToolCall] = field(default_factory=list)
    tool_errors: int = 0
    loop_warnings: int = 0
    max_turns_reached: bool = False
    total_usage: TokenUsage = field(default_factory=TokenUsage)


class ToolHandler:
    """Manages the tool-use loop: send to Claude, execute tools, send results back.

    Repeats until Claude stops requesting tools or max_turns is reached.
    Unknown tools return error tool_result (is_error=True).
    """

    def __init__(
        self,
        client: AnthropicClient,
        tool_handlers: dict[str, ToolHandlerFunc],
        compaction_client: CompactionClient | None = None,
        anthropic_raw_client: Any = None,
    ) -> None:
        self._client = client
        self._tool_handlers = tool_handlers
        self._compaction_client = compaction_client
        self._anthropic_raw_client = anthropic_raw_client

    async def run_loop(
        self,
        prompt: dict[str, Any],
        model: str,
        tools: list[dict[str, Any]],
        max_turns: int = 10,
        enable_loop_detection: bool = True,
        loop_threshold: int = 5,
        reasoning_effort: str | None = None,
    ) -> ToolLoopResult:
        """Run the tool-use loop until completion or max_turns.

        Args:
            prompt: Output from PromptBuilder.build().
            model: Model to use for all turns.
            tools: Tool definitions for the API call.
            max_turns: Maximum number of send-execute-respond cycles.
            enable_loop_detection: Whether to track per-resource repetition.
            loop_threshold: Number of calls before injecting guidance.
            reasoning_effort: Optional reasoning effort level passed to each
                send_message call in the loop ("high", "medium", "low").

        Returns:
            ToolLoopResult with final content, usage totals, and error counts.
        """
        all_tool_calls: list[ToolCall] = []
        total_usage = TokenUsage()
        tool_errors = 0
        loop_warnings = 0
        turns = 0
        tracker = ResourceEditTracker(threshold=loop_threshold) if enable_loop_detection else None

        # Working copy of prompt that we'll extend with tool results
        current_prompt = dict(prompt)
        current_messages = list(prompt["messages"])
        current_prompt["messages"] = current_messages

        for turn in range(max_turns):
            turns = turn + 1

            # Check if compaction is needed before sending to LLM
            if self._compaction_client and self._anthropic_raw_client:
                total_tokens = sum(
                    len(m.get("content", "").split())
                    if isinstance(m.get("content", ""), str)
                    else 0
                    for m in current_messages
                )
                if self._compaction_client.needs_compaction(total_tokens):
                    comp_result = await self._compaction_client.compact(
                        self._anthropic_raw_client,
                        current_prompt.get("system", ""),
                        current_messages,
                        operativo_id="unknown",
                    )
                    current_messages = comp_result.compacted_messages
                    current_prompt["messages"] = current_messages

            result: MessageResult = await self._client.send_message(
                current_prompt, model=model, tools=tools,
                reasoning_effort=reasoning_effort,
            )
            total_usage = total_usage + result.usage

            if result.stop_reason != "tool_use":
                # Model is done — return final content
                return ToolLoopResult(
                    final_content=result.content,
                    turns=turns,
                    tool_calls_made=all_tool_calls,
                    tool_errors=tool_errors,
                    loop_warnings=loop_warnings,
                    max_turns_reached=False,
                    total_usage=total_usage,
                )

            # Process tool calls
            all_tool_calls.extend(result.tool_calls)

            # Build assistant message with all content blocks (text + tool_use)
            assistant_content: list[dict[str, Any]] = []
            if result.content:
                assistant_content.append({"type": "text", "text": result.content})
            for tc in result.tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.input,
                })
            current_messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and collect results
            tool_results: list[dict[str, Any]] = []
            for tc in result.tool_calls:
                handler = self._tool_handlers.get(tc.name)
                if handler is None:
                    tool_errors += 1
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": f"Unknown tool: {tc.name}",
                        "is_error": True,
                    })
                else:
                    try:
                        output = await handler(tc.input)
                    except Exception as exc:
                        tool_errors += 1
                        output = f"Tool error: {exc}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": output,
                            "is_error": True,
                        })
                        continue

                    # Loop detection: check if this resource is being over-called
                    if tracker is not None:
                        guidance = tracker.record(tc.name, tc.input)
                        if guidance:
                            loop_warnings += 1
                            output = f"{output}\n\n{guidance}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": output,
                    })

            current_messages.append({"role": "user", "content": tool_results})

        # max_turns reached while still getting tool_use
        return ToolLoopResult(
            final_content=result.content,
            turns=turns,
            tool_calls_made=all_tool_calls,
            tool_errors=tool_errors,
            loop_warnings=loop_warnings,
            max_turns_reached=True,
            total_usage=total_usage,
        )
