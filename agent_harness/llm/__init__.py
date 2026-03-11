"""LLM client layer — AnthropicClient, ToolHandler, and supporting types.

All agents use this package to call LLMs. Supports Anthropic Vertex, OpenRouter,
and LiteLLM gateways via the provider-aware client factory.
"""

from agent_harness.llm.client import (
    AnthropicClient,
    MessageResult,
    TokenUsage,
    ToolCall,
)
from agent_harness.llm.client_factory import build_instructor_client
from agent_harness.llm.instructor_client import create_instructor_client
from agent_harness.llm.loop_detection import ResourceEditTracker
from agent_harness.llm.tool_handler import (
    ToolHandler,
    ToolHandlerFunc,
    ToolLoopResult,
)

__all__ = [
    "AnthropicClient",
    "MessageResult",
    "ResourceEditTracker",
    "build_instructor_client",
    "TokenUsage",
    "ToolCall",
    "ToolHandler",
    "ToolHandlerFunc",
    "ToolLoopResult",
    "create_instructor_client",
]
