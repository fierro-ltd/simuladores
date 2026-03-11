"""Anthropic API client with prompt translation and token tracking.

Translates PromptBuilder output to Anthropic Messages API format,
handles cache_control directives, and returns structured results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropicVertex


@dataclass(frozen=True)
class TokenUsage:
    """Token usage from a single API call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of input tokens served from cache (0.0-1.0)."""
        total = self.cache_creation_tokens + self.cache_read_tokens
        if total == 0:
            return 0.0
        return self.cache_read_tokens / total

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Combine usage from multiple calls."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
        )


@dataclass(frozen=True)
class ToolCall:
    """A tool_use block extracted from a Claude response."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class MessageResult:
    """Structured result from a single Claude API call."""

    content: str
    stop_reason: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""


class AnthropicClient:
    """Thin wrapper around Anthropic AsyncAnthropicVertex for prompt translation and token tracking.

    Translates PromptBuilder.build() output into Anthropic API kwargs,
    applies cache_control directives, and returns MessageResult.

    .. deprecated::
        Use ``create_instructor_client()`` from ``agent_harness.llm.instructor_client``
        for new code. This class will be removed in a future release once all agents
        are migrated to instructor-based structured outputs.
    """

    def __init__(self, project_id: str, region: str = "europe-west1",
                 default_model: str = "claude-sonnet-4-6") -> None:
        import httpx as _httpx
        self._client = AsyncAnthropicVertex(
            project_id=project_id,
            region=region,
            timeout=_httpx.Timeout(120.0, connect=30.0),
        )
        self._default_model = default_model
        self._total_usage = TokenUsage()

    @property
    def total_usage(self) -> TokenUsage:
        """Cumulative token usage across all send_message calls on this client."""
        return self._total_usage

    @staticmethod
    def _translate_prompt(
        prompt: dict[str, Any],
        model: str,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Convert PromptBuilder.build() output to Anthropic API kwargs.

        System prompt is wrapped in a list with cache_control: {"type": "ephemeral"}
        when the prompt's cache_config indicates system_cache is True.
        """
        cache_config = prompt.get("cache_control", {})
        system_text = prompt["system"]

        # Apply cache_control to system prompt when configured
        if cache_config.get("system_cache", False):
            system: str | list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_text

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": prompt["messages"],
        }

        if tools:
            kwargs["tools"] = tools

        return kwargs

    async def send_message(
        self,
        prompt: dict[str, Any],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
    ) -> MessageResult:
        """Send a prompt to Claude and return a structured MessageResult.

        Args:
            prompt: Output from PromptBuilder.build().
            model: Override model (uses default_model if None).
            tools: Tool definitions for the API call.
            max_tokens: Maximum tokens in the response.
            reasoning_effort: Optional reasoning effort level ("high", "medium", "low").
                Stored in request metadata for downstream use. The actual API
                integration will be wired when the beta parameter is confirmed.

        Returns:
            MessageResult with extracted content, tool_calls, and usage.
        """
        effective_model = model or self._default_model
        kwargs = self._translate_prompt(prompt, effective_model, max_tokens, tools)
        # reasoning_effort is accepted but not yet wired to the API.
        # Vertex AI rawPredict does not support metadata.reasoning_effort.
        import logging
        _logger = logging.getLogger(__name__)
        try:
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:
            # Log the tools and message count for debugging API errors
            tool_names = [t.get("name", "?") for t in (tools or [])]
            msg_count = len(kwargs.get("messages", []))
            _logger.error(
                "API call failed: model=%s tools=%s messages=%d error=%s",
                effective_model, tool_names, msg_count, exc,
            )
            raise

        # Extract text content and tool_use blocks
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        # Build token usage from response
        resp_usage = response.usage
        usage = TokenUsage(
            input_tokens=getattr(resp_usage, "input_tokens", 0),
            output_tokens=getattr(resp_usage, "output_tokens", 0),
            cache_creation_tokens=getattr(resp_usage, "cache_creation_input_tokens", 0),
            cache_read_tokens=getattr(resp_usage, "cache_read_input_tokens", 0),
        )

        self._total_usage = self._total_usage + usage

        return MessageResult(
            content="\n".join(text_parts),
            stop_reason=response.stop_reason,
            tool_calls=tool_calls,
            usage=usage,
            model=response.model,
        )
