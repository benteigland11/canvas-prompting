from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm_context_bundle import (
    LLMContextBundle,
    LLMContextBundleBuilder,
    LLMContextFunctionTool,
    LLMContextImagePart,
    LLMContextMessage,
    LLMContextServerTool,
    LLMContextTextPart,
    LLMContextTool,
    LLMContextToolCall,
    build_context_bundle,
)


# ---------------------------------------------------------------------------
# v1.0 behaviour — preserved verbatim so existing consumers keep working
# ---------------------------------------------------------------------------


def test_bundle_builder_collects_system_messages_tools_and_metadata() -> None:
    builder = LLMContextBundleBuilder()
    builder.set_system_prompt("You are Jax.")
    builder.add_message(role="user", content="Read AGENTS.md")
    builder.add_tool(
        tool_id="read_file",
        display_name="Read File",
        description="Read a file from the workspace.",
    )
    builder.set_metadata(model="grok", workspace="/tmp/project")

    bundle = builder.build()

    assert bundle.system_prompt == "You are Jax."
    assert bundle.messages[0].role == "user"
    assert bundle.tools[0].tool_id == "read_file"
    assert bundle.metadata == {"model": "grok", "workspace": "/tmp/project"}


def test_message_rejects_unknown_role() -> None:
    with pytest.raises(ValueError, match="unsupported message role 'planner'"):
        LLMContextMessage(role="planner", content="hello")


def test_message_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="message content must not be empty"):
        LLMContextMessage(role="user", content="   ")


def test_tool_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="tool_id must not be empty"):
        LLMContextTool(tool_id="", display_name="Read File", description="Read a file.")


def test_build_context_bundle_serializes_to_dict_and_json() -> None:
    bundle = build_context_bundle(
        system_prompt="You are Jax.",
        messages=(LLMContextMessage(role="user", content="Read AGENTS.md"),),
        tools=(
            LLMContextTool(
                tool_id="read_file",
                display_name="Read File",
                description="Read a file from the workspace.",
            ),
        ),
        metadata={"workspace": "/tmp/project"},
    )

    payload = bundle.to_dict()
    rendered = bundle.to_json()

    assert payload["system_prompt"] == "You are Jax."
    assert payload["messages"][0]["role"] == "user"
    # v1.1: tools live under function_tools in the serialized form.
    assert payload["function_tools"][0]["tool_id"] == "read_file"
    assert payload["server_tools"] == []
    assert '"workspace": "/tmp/project"' in rendered


def test_bundle_tools_property_aliases_function_tools() -> None:
    """v1.0 consumers read bundle.tools — keep that alias pointing at
    function_tools so they don't break."""
    bundle = build_context_bundle(
        function_tools=(
            LLMContextFunctionTool(
                tool_id="read_file",
                display_name="Read File",
                description="Read a file.",
            ),
        ),
    )
    assert bundle.tools == bundle.function_tools
    assert len(bundle.tools) == 1
    assert bundle.tools[0].tool_id == "read_file"


def test_llm_context_tool_is_alias_for_function_tool() -> None:
    """LLMContextTool is kept as an alias so existing imports resolve."""
    assert LLMContextTool is LLMContextFunctionTool


# ---------------------------------------------------------------------------
# v1.1 — LLMContextToolCall
# ---------------------------------------------------------------------------


def test_tool_call_requires_id_and_name() -> None:
    with pytest.raises(ValueError, match="tool_call id must not be empty"):
        LLMContextToolCall(id="", name="read_file")
    with pytest.raises(ValueError, match="tool_call name must not be empty"):
        LLMContextToolCall(id="call_1", name="  ")


def test_tool_call_to_dict_round_trip() -> None:
    call = LLMContextToolCall(
        id="call_123",
        name="read_file",
        arguments='{"path": "AGENTS.md"}',
        metadata={"server_tool": False},
    )
    payload = call.to_dict()
    assert payload == {
        "id": "call_123",
        "name": "read_file",
        "arguments": '{"path": "AGENTS.md"}',
        "metadata": {"server_tool": False},
    }


def test_tool_call_arguments_default_empty() -> None:
    """Partial tool_calls (mid-stream) have no arguments yet — that must
    be valid, not a hard error."""
    call = LLMContextToolCall(id="call_1", name="read_file")
    assert call.arguments == ""


# ---------------------------------------------------------------------------
# v1.1 — LLMContextMessage with tool_calls
# ---------------------------------------------------------------------------


def test_assistant_message_with_tool_calls_allows_empty_content() -> None:
    """The core bug we fixed: models routinely emit an assistant turn
    that has only tool_calls and no text content. v1.0 rejected it."""
    call = LLMContextToolCall(id="call_1", name="read_file", arguments='{"path": "a.md"}')
    msg = LLMContextMessage(role="assistant", content="", tool_calls=(call,))
    assert msg.content == ""
    assert msg.tool_calls == (call,)


def test_assistant_message_with_tool_calls_and_content() -> None:
    """A model can also emit text AND tool_calls in the same turn."""
    call = LLMContextToolCall(id="call_1", name="read_file")
    msg = LLMContextMessage(
        role="assistant",
        content="Let me read that for you.",
        tool_calls=(call,),
    )
    assert msg.content == "Let me read that for you."
    assert len(msg.tool_calls) == 1


def test_assistant_message_empty_content_without_tool_calls_still_rejected() -> None:
    """Empty content is the exception, not the rule. An assistant turn
    with neither content nor tool_calls is still garbage."""
    with pytest.raises(ValueError, match="content must not be empty"):
        LLMContextMessage(role="assistant", content="")


def test_user_message_with_tool_calls_rejected() -> None:
    """Only assistant turns can carry tool_calls. A user message with
    tool_calls is a sign the caller is confused about roles."""
    call = LLMContextToolCall(id="call_1", name="read_file")
    with pytest.raises(ValueError, match="tool_calls may only appear on assistant messages"):
        LLMContextMessage(role="user", content="hello", tool_calls=(call,))


def test_tool_call_id_only_on_tool_role() -> None:
    """tool_call_id pairs a tool result with an assistant call — it
    doesn't belong on user or assistant turns."""
    with pytest.raises(ValueError, match="tool_call_id may only appear on tool messages"):
        LLMContextMessage(role="user", content="hello", tool_call_id="call_1")


def test_tool_message_round_trip() -> None:
    msg = LLMContextMessage(
        role="tool",
        content="file contents",
        tool_call_id="call_1",
        name="read_file",
    )
    payload = msg.to_dict()
    assert payload["role"] == "tool"
    assert payload["content"] == "file contents"
    assert payload["tool_call_id"] == "call_1"
    assert payload["name"] == "read_file"


def test_assistant_tool_call_message_to_dict_includes_tool_calls() -> None:
    call = LLMContextToolCall(id="call_1", name="read_file", arguments='{"path": "a.md"}')
    msg = LLMContextMessage(role="assistant", content="", tool_calls=(call,))
    payload = msg.to_dict()
    assert payload["role"] == "assistant"
    assert payload["content"] == ""
    assert payload["tool_calls"] == [
        {
            "id": "call_1",
            "name": "read_file",
            "arguments": '{"path": "a.md"}',
        }
    ]


# ---------------------------------------------------------------------------
# v1.1 — LLMContextServerTool and the function/server split
# ---------------------------------------------------------------------------


def test_server_tool_basic_fields() -> None:
    tool = LLMContextServerTool(
        tool_id="web_search",
        display_name="Web Search",
        description="Vendor-hosted web search.",
        config={"max_results": 5},
    )
    assert tool.tool_id == "web_search"
    assert tool.config == {"max_results": 5}


def test_server_tool_to_dict_omits_empty_config() -> None:
    tool = LLMContextServerTool(
        tool_id="x_search",
        display_name="X Search",
        description="Vendor-hosted X search.",
    )
    payload = tool.to_dict()
    assert "config" not in payload
    assert payload["tool_id"] == "x_search"


def test_server_tool_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="tool_id must not be empty"):
        LLMContextServerTool(tool_id="", display_name="X", description="x")


def test_function_tool_and_server_tool_kept_separate_on_bundle() -> None:
    builder = LLMContextBundleBuilder()
    builder.add_function_tool(
        tool_id="read_file",
        display_name="Read File",
        description="Read a file.",
    )
    builder.add_server_tool(
        tool_id="web_search",
        display_name="Web Search",
        description="Vendor-hosted web search.",
        config={"max_results": 5},
    )

    bundle = builder.build()

    assert len(bundle.function_tools) == 1
    assert len(bundle.server_tools) == 1
    assert bundle.function_tools[0].tool_id == "read_file"
    assert bundle.server_tools[0].tool_id == "web_search"

    payload = bundle.to_dict()
    assert payload["function_tools"][0]["tool_id"] == "read_file"
    assert payload["server_tools"][0]["tool_id"] == "web_search"
    assert payload["server_tools"][0]["config"] == {"max_results": 5}


def test_builder_add_tool_is_backwards_compat_alias() -> None:
    """v1.0 callers used add_tool — it must still land a function tool."""
    builder = LLMContextBundleBuilder()
    builder.add_tool(
        tool_id="read_file",
        display_name="Read File",
        description="Read a file.",
    )
    bundle = builder.build()
    assert len(bundle.function_tools) == 1
    assert bundle.function_tools[0].tool_id == "read_file"


def test_builder_extend_tools_is_backwards_compat_alias() -> None:
    builder = LLMContextBundleBuilder()
    builder.extend_tools(
        [
            LLMContextFunctionTool(
                tool_id="read_file",
                display_name="Read File",
                description="Read a file.",
            ),
        ]
    )
    bundle = builder.build()
    assert len(bundle.function_tools) == 1


def test_builder_extend_server_tools() -> None:
    builder = LLMContextBundleBuilder()
    builder.extend_server_tools(
        [
            LLMContextServerTool(
                tool_id="web_search",
                display_name="Web Search",
                description="Vendor-hosted web search.",
            ),
        ]
    )
    bundle = builder.build()
    assert len(bundle.server_tools) == 1


# ---------------------------------------------------------------------------
# v1.1 — builder convenience helpers for multi-turn tool conversations
# ---------------------------------------------------------------------------


def test_builder_assistant_tool_call_message_helper() -> None:
    """The convenience helper builds the common assistant-with-tool_calls
    shape without forcing the caller to pass role explicitly."""
    builder = LLMContextBundleBuilder()
    call = LLMContextToolCall(id="call_1", name="read_file")
    builder.add_assistant_tool_call_message(tool_calls=(call,))
    bundle = builder.build()
    assert bundle.messages[0].role == "assistant"
    assert bundle.messages[0].tool_calls == (call,)
    assert bundle.messages[0].content == ""


def test_builder_tool_result_message_helper() -> None:
    builder = LLMContextBundleBuilder()
    builder.add_tool_result_message(
        tool_call_id="call_1",
        content="file contents here",
        name="read_file",
    )
    bundle = builder.build()
    assert bundle.messages[0].role == "tool"
    assert bundle.messages[0].tool_call_id == "call_1"
    assert bundle.messages[0].content == "file contents here"


def test_full_multi_turn_tool_conversation_round_trip() -> None:
    """End-to-end: build a bundle that represents a complete tool-use
    conversation (user asks → assistant calls tool → tool result →
    assistant answers). v1.0 couldn't represent turns 2 and 3."""
    builder = LLMContextBundleBuilder()
    builder.set_system_prompt("You are Jax.")
    builder.add_function_tool(
        tool_id="read_file",
        display_name="Read File",
        description="Read a file.",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )

    # Turn 1: user asks.
    builder.add_message(role="user", content="What's in AGENTS.md?")

    # Turn 2: assistant calls the tool (empty content, only tool_calls).
    call = LLMContextToolCall(
        id="call_1",
        name="read_file",
        arguments='{"path": "AGENTS.md"}',
    )
    builder.add_assistant_tool_call_message(tool_calls=(call,))

    # Turn 3: tool result comes back.
    builder.add_tool_result_message(
        tool_call_id="call_1",
        content="# AGENTS.md\n\nThis is the agents doc.",
        name="read_file",
    )

    # Turn 4: assistant answers using the tool result.
    builder.add_message(role="assistant", content="The file describes the agents.")

    bundle = builder.build()

    assert len(bundle.messages) == 4
    assert bundle.messages[0].role == "user"
    assert bundle.messages[1].role == "assistant"
    assert bundle.messages[1].tool_calls[0].name == "read_file"
    assert bundle.messages[2].role == "tool"
    assert bundle.messages[2].tool_call_id == "call_1"
    assert bundle.messages[3].role == "assistant"

    # Serialization should survive the round trip.
    payload = bundle.to_dict()
    assert payload["messages"][1]["tool_calls"][0]["id"] == "call_1"
    assert payload["messages"][2]["tool_call_id"] == "call_1"


# ---------------------------------------------------------------------------
# v1.1 — build_context_bundle kwargs
# ---------------------------------------------------------------------------


def test_build_context_bundle_accepts_split_tools() -> None:
    bundle = build_context_bundle(
        function_tools=(
            LLMContextFunctionTool(
                tool_id="read_file",
                display_name="Read File",
                description="Read a file.",
            ),
        ),
        server_tools=(
            LLMContextServerTool(
                tool_id="web_search",
                display_name="Web Search",
                description="Vendor-hosted web search.",
            ),
        ),
    )
    assert len(bundle.function_tools) == 1
    assert len(bundle.server_tools) == 1


def test_build_context_bundle_tools_kwarg_back_compat() -> None:
    """Passing the deprecated `tools=` kwarg routes into function_tools,
    so v1.0 call sites keep working."""
    bundle = build_context_bundle(
        tools=(
            LLMContextTool(
                tool_id="read_file",
                display_name="Read File",
                description="Read a file.",
            ),
        ),
    )
    assert len(bundle.function_tools) == 1
    assert len(bundle.server_tools) == 0
    assert bundle.function_tools[0].tool_id == "read_file"


def test_build_context_bundle_merges_tools_and_function_tools() -> None:
    """Mixing deprecated `tools=` with new `function_tools=` should
    concatenate — nobody gets dropped on the floor."""
    bundle = build_context_bundle(
        function_tools=(
            LLMContextFunctionTool(
                tool_id="a",
                display_name="A",
                description="a",
            ),
        ),
        tools=(
            LLMContextFunctionTool(
                tool_id="b",
                display_name="B",
                description="b",
            ),
        ),
    )
    assert [t.tool_id for t in bundle.function_tools] == ["a", "b"]


# ---------------------------------------------------------------------------
# v1.2 — multimodal content parts
# ---------------------------------------------------------------------------


def test_text_part_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="text must not be empty"):
        LLMContextTextPart(text="")


def test_text_part_to_dict_shape() -> None:
    part = LLMContextTextPart(text="Look at this image:")
    assert part.to_dict() == {"type": "text", "text": "Look at this image:"}


def test_image_part_accepts_plain_url_string() -> None:
    part = LLMContextImagePart(image_url="https://example.com/cat.png")
    payload = part.to_dict()
    assert payload == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/cat.png"},
    }


def test_image_part_accepts_data_url_string() -> None:
    """Inline base64 images are the common T12 case — they arrive as data:
    URLs and must round-trip unchanged."""
    data_url = "data:image/png;base64,iVBORw0KG..."
    part = LLMContextImagePart(image_url=data_url)
    payload = part.to_dict()
    assert payload["image_url"]["url"] == data_url


def test_image_part_accepts_dict_with_detail_hint() -> None:
    """OpenAI and xAI accept a dict form with a detail hint; the widget
    must preserve the full dict, not just the url."""
    part = LLMContextImagePart(
        image_url={"url": "https://example.com/cat.png", "detail": "auto"},
    )
    payload = part.to_dict()
    assert payload == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/cat.png", "detail": "auto"},
    }


def test_image_part_rejects_empty_string_url() -> None:
    with pytest.raises(ValueError, match="image_url must not be empty"):
        LLMContextImagePart(image_url="   ")


def test_image_part_rejects_dict_without_url_key() -> None:
    with pytest.raises(ValueError, match="must contain a non-empty 'url' key"):
        LLMContextImagePart(image_url={"detail": "auto"})


def test_image_part_rejects_non_string_non_dict_url() -> None:
    with pytest.raises(ValueError, match="must be a string or a dict"):
        LLMContextImagePart(image_url=42)  # type: ignore[arg-type]


def test_multimodal_message_with_text_and_image_parts() -> None:
    """The real-world T12 shape: a user turn with inline text and one or
    more image parts. v1.1 would reject this because .content wasn't a str."""
    msg = LLMContextMessage(
        role="user",
        content=(
            LLMContextTextPart(text="What's in this image?"),
            LLMContextImagePart(image_url="https://example.com/cat.png"),
        ),
    )
    assert msg.role == "user"
    assert len(msg.content) == 2
    assert isinstance(msg.content[0], LLMContextTextPart)
    assert isinstance(msg.content[1], LLMContextImagePart)


def test_multimodal_message_accepts_list_content_normalizes_to_tuple() -> None:
    """Callers naturally pass a list — the dataclass normalizes to tuple
    so the frozen instance stays immutable."""
    msg = LLMContextMessage(
        role="user",
        content=[
            LLMContextTextPart(text="Here:"),
            LLMContextImagePart(image_url="https://example.com/a.png"),
        ],
    )
    assert isinstance(msg.content, tuple)
    assert len(msg.content) == 2


def test_multimodal_message_rejects_empty_parts_list() -> None:
    """Zero parts is the multimodal equivalent of an empty string —
    nothing useful for the model to work with."""
    with pytest.raises(ValueError, match="content must not be empty"):
        LLMContextMessage(role="user", content=())


def test_multimodal_message_rejects_invalid_part_type() -> None:
    with pytest.raises(ValueError, match="must be LLMContextTextPart"):
        LLMContextMessage(
            role="user",
            content=({"type": "text", "text": "naked dict"},),  # type: ignore[arg-type]
        )


def test_multimodal_message_to_dict_serializes_parts() -> None:
    msg = LLMContextMessage(
        role="user",
        content=(
            LLMContextTextPart(text="Here:"),
            LLMContextImagePart(
                image_url={"url": "https://example.com/a.png", "detail": "high"}
            ),
        ),
    )
    payload = msg.to_dict()
    assert payload["role"] == "user"
    assert isinstance(payload["content"], list)
    assert payload["content"][0] == {"type": "text", "text": "Here:"}
    assert payload["content"][1]["type"] == "image_url"
    assert payload["content"][1]["image_url"]["url"] == "https://example.com/a.png"
    assert payload["content"][1]["image_url"]["detail"] == "high"


def test_builder_add_multimodal_message_helper() -> None:
    """The convenience helper makes multimodal intent explicit at the
    call site while still routing through add_message underneath."""
    builder = LLMContextBundleBuilder()
    builder.add_multimodal_message(
        role="user",
        parts=[
            LLMContextTextPart(text="What is this?"),
            LLMContextImagePart(image_url="data:image/png;base64,AAAA"),
        ],
    )
    bundle = builder.build()
    assert len(bundle.messages) == 1
    assert bundle.messages[0].role == "user"
    assert isinstance(bundle.messages[0].content, tuple)
    assert len(bundle.messages[0].content) == 2


def test_builder_add_message_with_list_content_directly() -> None:
    """add_message must also accept list content — not every caller
    wants the add_multimodal_message helper."""
    builder = LLMContextBundleBuilder()
    builder.add_message(
        role="user",
        content=[
            LLMContextTextPart(text="Compare:"),
            LLMContextImagePart(image_url="https://a.png"),
            LLMContextImagePart(image_url="https://b.png"),
        ],
    )
    bundle = builder.build()
    assert len(bundle.messages[0].content) == 3


def test_text_only_messages_still_accept_plain_string() -> None:
    """v1.0/v1.1 call sites that pass content=str must keep working
    unchanged — no migration forced for text-only paths."""
    builder = LLMContextBundleBuilder()
    builder.add_message(role="user", content="Just a string, please.")
    bundle = builder.build()
    assert bundle.messages[0].content == "Just a string, please."
    # Serialization format for string content is also unchanged.
    assert bundle.to_dict()["messages"][0]["content"] == "Just a string, please."
