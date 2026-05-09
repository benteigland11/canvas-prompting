"""
Example usage of the LLM Provider Interface.

Demonstrates how a concrete vendor adapter implements the LLMClient Protocol
and how a consumer depends only on the canonical types. Uses a fake
in-memory implementation — no network calls, no API keys.

Run: python examples/example_usage.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm_provider_interface import (
    ChatRequest,
    ChatResponse,
    ContentDelta,
    LLMClient,
    Message,
    ServerToolAnnounce,
    ServerToolResult,
    StreamEnd,
    StreamError,
    StreamEvent,
    StreamStart,
    Usage,
    UsageEvent,
)


# ---------------------------------------------------------------------------
# A fake vendor adapter — implements LLMClient with hardcoded data
# ---------------------------------------------------------------------------


class FakeVendorClient:
    """A pretend LLM vendor adapter. Returns canned responses."""

    max_context = 8192

    async def chat(self, request: ChatRequest) -> ChatResponse:
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            "",
        )
        reply = f"You said: {last_user!r}"
        return ChatResponse(
            content=reply,
            usage=Usage(
                input_tokens=len(str(last_user)),
                output_tokens=len(reply),
                total_tokens=len(str(last_user)) + len(reply),
            ),
            stop_reason="stop",
            model=request.model,
        )

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        return self._stream(request)

    async def _stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield StreamStart(model=request.model, stream_id="fake-1")

        # Pretend the model kicks off a server-side web search.
        if request.server_tools and any(t.name == "web_search" for t in request.server_tools):
            yield ServerToolAnnounce(
                tool_name="web_search",
                source={"query": "pretend search"},
            )
            yield ServerToolResult(
                tool_name="web_search",
                data=[{"url": "https://example.com", "title": "Example"}],
            )

        reply = "hello from fake vendor"
        for word in reply.split():
            yield ContentDelta(text=word + " ")

        usage = Usage(input_tokens=10, output_tokens=len(reply), total_tokens=10 + len(reply))
        yield UsageEvent(usage=usage)
        yield StreamEnd(stop_reason="stop", usage=usage)

    def supports(self, capability: str) -> bool:
        return capability in {
            "streaming",
            "vision",
            "server_tool:web_search",
            "json_mode",
        }


# ---------------------------------------------------------------------------
# Consumer code depends only on the Protocol — not on FakeVendorClient
# ---------------------------------------------------------------------------


async def run_non_streaming(client: LLMClient) -> None:
    req = ChatRequest(
        messages=[
            Message(role="system", content="You are helpful."),
            Message(role="user", content="What is 2+2?"),
            Message(role="tool", content='{"answer":4}', name="calculator", tool_call_id="call_1"),
        ],
        model="fake-model-1",
        temperature=0.7,
        max_tokens=100,
    )
    resp = await client.chat(req)
    print("=== non-streaming ===")
    print(f"content: {resp.content}")
    print(f"usage: {resp.usage.as_dict()}")
    print(f"stop_reason: {resp.stop_reason}")


async def run_streaming(client: LLMClient) -> None:
    from src.llm_provider_interface import ServerTool

    req = ChatRequest(
        messages=[Message(role="user", content="Find me news.")],
        model="fake-model-1",
        server_tools=[ServerTool(name="web_search")] if client.supports("server_tool:web_search") else None,
    )

    print("\n=== streaming ===")
    buffered = ""
    async for event in client.stream_chat(req):
        match event:
            case StreamStart(model=model):
                print(f"[start] model={model}")
            case ContentDelta(text=text):
                buffered += text
            case ServerToolAnnounce(tool_name=name, source=src):
                print(f"[server_tool_announce] {name} {src}")
            case ServerToolResult(tool_name=name, data=data):
                print(f"[server_tool_result] {name} got {len(data)} result(s)")
            case UsageEvent(usage=usage):
                print(f"[usage] {usage.as_dict() if usage else None}")
            case StreamEnd(stop_reason=reason):
                print(f"[end] stop_reason={reason}")
            case StreamError(message=msg):
                print(f"[error] {msg}")
                break
    print(f"buffered content: {buffered!r}")


async def main() -> None:
    client: LLMClient = FakeVendorClient()
    assert isinstance(client, LLMClient), "FakeVendorClient must satisfy LLMClient Protocol"

    print(f"capabilities: streaming={client.supports('streaming')} "
          f"web_search={client.supports('server_tool:web_search')} "
          f"max_context={client.max_context}")

    await run_non_streaming(client)
    await run_streaming(client)


if __name__ == "__main__":
    asyncio.run(main())
