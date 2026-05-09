"""Tests for the LLM Provider Interface widget.

These verify the canonical shapes are constructable, the discriminated
unions dispatch correctly, and that a fake in-memory LLMClient satisfies
the Protocol via runtime_checkable.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm_provider_interface import (
    ChatRequest,
    ChatResponse,
    ContentDelta,
    FunctionTool,
    FunctionToolCall,
    ImagePart,
    LLMClient,
    Message,
    ReasoningDelta,
    ServerTool,
    ServerToolAnnounce,
    ServerToolResult,
    StreamEnd,
    StreamError,
    StreamEvent,
    StreamStart,
    TextPart,
    ToolCall,
    Usage,
    UsageEvent,
)


# ---------------------------------------------------------------------------
# Message / content parts
# ---------------------------------------------------------------------------


def test_message_accepts_plain_string_content() -> None:
    msg = Message(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"


def test_message_accepts_tool_role_and_linking_fields() -> None:
    msg = Message(role="tool", content='{"ok":true}', name="read_file", tool_call_id="call_1")
    assert msg.role == "tool"
    assert msg.name == "read_file"
    assert msg.tool_call_id == "call_1"


def test_message_accepts_content_parts_list() -> None:
    parts = [
        TextPart(text="look at this:"),
        ImagePart(image_url={"url": "https://example.com/x.png", "detail": "auto"}),
    ]
    msg = Message(role="user", content=parts)
    assert isinstance(msg.content, list)
    assert len(msg.content) == 2
    assert msg.content[0].type == "text"
    assert msg.content[1].type == "image_url"


def test_text_part_defaults_type_tag() -> None:
    assert TextPart(text="hi").type == "text"


def test_image_part_defaults_type_tag() -> None:
    assert ImagePart(image_url={"url": "u"}).type == "image_url"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def test_function_tool_round_trip() -> None:
    tool = FunctionTool(
        name="get_weather",
        description="Lookup current weather",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    assert tool.name == "get_weather"
    assert tool.parameters["type"] == "object"


def test_server_tool_accepts_bare_name() -> None:
    tool = ServerTool(name="web_search")
    assert tool.name == "web_search"
    assert tool.config is None


def test_server_tool_accepts_vendor_config_passthrough() -> None:
    tool = ServerTool(
        name="web_search",
        config={"allowed_domains": ["example.com"], "enable_image_understanding": True},
    )
    assert tool.config["allowed_domains"] == ["example.com"]


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


def test_usage_defaults_to_zero() -> None:
    u = Usage()
    assert u.input_tokens == 0
    assert u.output_tokens == 0
    assert u.total_tokens == 0
    assert u.reasoning_tokens == 0
    assert u.cached_tokens == 0
    assert u.image_tokens == 0


def test_usage_as_dict_round_trip() -> None:
    u = Usage(
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        reasoning_tokens=20,
        cached_tokens=10,
        image_tokens=5,
    )
    d = u.as_dict()
    assert d == {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "reasoning_tokens": 20,
        "cached_tokens": 10,
        "image_tokens": 5,
    }


# ---------------------------------------------------------------------------
# ChatRequest / ChatResponse
# ---------------------------------------------------------------------------


def test_chat_request_minimal() -> None:
    req = ChatRequest(
        messages=[Message(role="user", content="hi")],
        model="test-model",
    )
    assert req.model == "test-model"
    assert req.temperature is None
    assert req.tools is None
    assert req.server_tools is None


def test_chat_request_full_surface() -> None:
    req = ChatRequest(
        messages=[Message(role="user", content="hi")],
        model="test-model",
        temperature=0.7,
        max_tokens=512,
        top_p=0.95,
        top_k=40,
        frequency_penalty=0.1,
        presence_penalty=0.0,
        stop=["END"],
        seed=42,
        response_format="json_object",
        tools=[FunctionTool(name="f", description="d", parameters={})],
        server_tools=[ServerTool(name="web_search")],
        tool_choice="auto",
    )
    assert req.temperature == 0.7
    assert req.tools[0].name == "f"
    assert req.server_tools[0].name == "web_search"
    assert req.tool_choice == "auto"


def test_chat_response_construction() -> None:
    resp = ChatResponse(
        content="hello back",
        usage=Usage(input_tokens=5, output_tokens=3, total_tokens=8),
        stop_reason="stop",
        model="test-model",
    )
    assert resp.content == "hello back"
    assert resp.usage.total_tokens == 8
    assert resp.tool_calls is None


def test_chat_response_with_tool_calls() -> None:
    resp = ChatResponse(
        content="",
        usage=Usage(),
        stop_reason="tool_calls",
        tool_calls=[ToolCall(call_id="c1", name="f", arguments='{"x":1}')],
    )
    assert resp.stop_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "f"


# ---------------------------------------------------------------------------
# StreamEvent discriminated union
# ---------------------------------------------------------------------------


def test_all_nine_stream_event_variants_have_distinct_type_tags() -> None:
    events: list[StreamEvent] = [
        StreamStart(),
        ContentDelta(text="hi"),
        ReasoningDelta(text="hmm"),
        FunctionToolCall(call_id="c1", name="f", arguments="{}"),
        ServerToolAnnounce(tool_name="web_search"),
        ServerToolResult(tool_name="web_search", data=[{"url": "u"}]),
        UsageEvent(usage=Usage()),
        StreamEnd(stop_reason="stop"),
        StreamError(message="oops"),
    ]
    type_tags = [e.type for e in events]
    assert len(type_tags) == len(set(type_tags)), "all type tags must be unique"
    assert set(type_tags) == {
        "start",
        "content_delta",
        "reasoning_delta",
        "function_tool_call",
        "server_tool_announce",
        "server_tool_result",
        "usage",
        "end",
        "error",
    }


def test_stream_event_match_dispatch() -> None:
    """Exercise a match/case dispatcher — this is the pattern hot-path
    consumers will use to replace the current key-presence chunk-reading."""

    def summarise(event: StreamEvent) -> str:
        match event:
            case ContentDelta(text=text):
                return f"text:{text}"
            case ReasoningDelta(text=text):
                return f"reasoning:{text}"
            case ServerToolAnnounce(tool_name=name):
                return f"tool_start:{name}"
            case ServerToolResult(tool_name=name, data=data):
                return f"tool_end:{name}:{len(data)}"
            case UsageEvent(usage=usage):
                return f"usage:{usage.total_tokens if usage else 0}"
            case StreamEnd(stop_reason=reason):
                return f"end:{reason}"
            case StreamError(message=msg):
                return f"error:{msg}"
            case _:
                return "other"

    assert summarise(ContentDelta(text="hi")) == "text:hi"
    assert summarise(ReasoningDelta(text="think")) == "reasoning:think"
    assert summarise(ServerToolAnnounce(tool_name="web_search")) == "tool_start:web_search"
    assert (
        summarise(ServerToolResult(tool_name="web_search", data=[{"url": "u"}, {"url": "v"}]))
        == "tool_end:web_search:2"
    )
    assert summarise(UsageEvent(usage=Usage(total_tokens=42))) == "usage:42"
    assert summarise(StreamEnd(stop_reason="length")) == "end:length"
    assert summarise(StreamError(message="boom")) == "error:boom"


def test_content_delta_default_text_is_empty() -> None:
    assert ContentDelta().text == ""


def test_stream_end_default_stop_reason() -> None:
    assert StreamEnd().stop_reason == "stop"


def test_stream_error_default_not_recoverable() -> None:
    assert StreamError().recoverable is False


# ---------------------------------------------------------------------------
# LLMClient Protocol — a fake in-memory implementation
# ---------------------------------------------------------------------------


class _FakeClient:
    """In-memory LLMClient implementation for Protocol conformance tests."""

    max_context = 8192

    def __init__(self, reply: str = "hello world", caps: Optional[set[str]] = None) -> None:
        self._reply = reply
        self._caps = caps or {"streaming", "vision"}

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            content=self._reply,
            usage=Usage(input_tokens=1, output_tokens=len(self._reply), total_tokens=1 + len(self._reply)),
            model=request.model,
        )

    async def _stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield StreamStart(model=request.model)
        for ch in self._reply:
            yield ContentDelta(text=ch)
        yield UsageEvent(usage=Usage(input_tokens=1, output_tokens=len(self._reply)))
        yield StreamEnd(stop_reason="stop")

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        return self._stream(request)

    def supports(self, capability: str) -> bool:
        return capability in self._caps


def test_fake_client_satisfies_protocol() -> None:
    client = _FakeClient()
    assert isinstance(client, LLMClient)


def test_fake_client_non_streaming() -> None:
    client = _FakeClient(reply="hi")
    req = ChatRequest(
        messages=[Message(role="user", content="ping")],
        model="fake-model",
    )
    resp = asyncio.run(client.chat(req))
    assert resp.content == "hi"
    assert resp.usage.output_tokens == 2
    assert resp.model == "fake-model"


def test_fake_client_streaming_produces_canonical_events() -> None:
    client = _FakeClient(reply="ab")
    req = ChatRequest(
        messages=[Message(role="user", content="ping")],
        model="fake-model",
    )

    async def collect() -> list[StreamEvent]:
        events: list[StreamEvent] = []
        async for ev in client.stream_chat(req):
            events.append(ev)
        return events

    events = asyncio.run(collect())
    types = [e.type for e in events]
    assert types == ["start", "content_delta", "content_delta", "usage", "end"]
    assert isinstance(events[-1], StreamEnd)
    assert events[-1].stop_reason == "stop"


def test_fake_client_capability_check() -> None:
    client = _FakeClient()
    assert client.supports("streaming") is True
    assert client.supports("vision") is True
    assert client.supports("server_tool:web_search") is False
