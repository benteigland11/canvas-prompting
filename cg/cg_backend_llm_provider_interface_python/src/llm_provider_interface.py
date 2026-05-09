"""
LLM Provider Interface — vendor-agnostic contract for chat completion backends.

Defines the canonical dataclasses (ChatRequest, ChatResponse, Usage, Message,
FunctionTool, ServerTool, StreamEvent union) and the LLMClient Protocol that
concrete vendor adapters (xAI, OpenAI, Anthropic, llama-server, ...) implement.

Consumers depend on the Protocol, not on any specific vendor SDK. Swap vendors
by swapping the adapter wiring.

Pure types — no runtime vendor code.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Protocol, Union, runtime_checkable


# ---------------------------------------------------------------------------
# Messages (canonical normalized content parts)
# ---------------------------------------------------------------------------

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class TextPart:
    """A text fragment inside a message's content array."""
    text: str
    type: Literal["text"] = "text"


@dataclass
class ImagePart:
    """An image reference inside a message's content array.

    `image_url` is kept as a dict (e.g. `{"url": "...", "detail": "auto"}`) to
    preserve vendor-specific extensions without forcing a canonical sub-shape.
    """
    image_url: dict
    type: Literal["image_url"] = "image_url"


ContentPart = Union[TextPart, ImagePart]


@dataclass
class Message:
    """A single chat message.

    Content may be a plain string (simple text) or a list of content parts
    (multimodal). `tool` is included as a first-class role so app-owned tool
    loops can feed tool results back through provider adapters without
    degrading them into fake user messages. `name` and `tool_call_id` are
    optional linking fields for providers that need to associate a tool
    result with a prior tool call. This is a canonical transport shape for
    adapters, not a claim that every vendor exposes the same native message
    schema.
    """
    role: Role
    content: Union[str, list[ContentPart]]
    name: str = ""
    tool_call_id: str = ""


# ---------------------------------------------------------------------------
# Tools — two distinct categories
# ---------------------------------------------------------------------------


@dataclass
class FunctionTool:
    """A client-side function tool.

    The caller is responsible for executing the function when the model
    requests it, and feeding the result back on a subsequent turn.
    JSON schema is the cross-vendor lingua franca.
    """
    name: str
    description: str
    parameters: dict  # JSON schema


@dataclass
class ServerTool:
    """A server-side tool executed by the vendor's infrastructure.

    Examples: xAI `web_search` / `x_search`, Gemini grounding, OpenAI web
    browsing, Anthropic web search / computer use. Results come back as
    events in the stream rather than as tool-call messages.

    `config` is a vendor-specific passthrough dict (e.g. `allowed_domains`,
    `from_date`, ...). Canonicalising every vendor's server-tool params is a
    rabbit hole; adapters map this dict onto their SDK.
    """
    name: str
    config: Optional[dict] = None


ToolChoice = Union[Literal["auto", "none", "required"], str]


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


@dataclass
class Usage:
    """Canonical token usage report.

    Adapters are responsible for normalising vendor-specific field names
    (`prompt_tokens` vs `input_tokens`, nested `completion_tokens_details`,
    etc.) onto this shape before yielding it.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    image_tokens: int = 0

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "image_tokens": self.image_tokens,
        }


# ---------------------------------------------------------------------------
# ChatRequest / ChatResponse
# ---------------------------------------------------------------------------


@dataclass
class ChatRequest:
    """A single chat completion request.

    Every field is optional except `messages` and `model`. Adapters ignore
    parameters their backend doesn't support — callers negotiate capabilities
    via `LLMClient.supports()` when behaviour matters.

    `tools` and `server_tools` are deliberately separate: function tools are
    executed by the caller, server tools by the vendor. The concerns are
    different enough to warrant distinct fields.

    `response_format` is a vendor-passthrough: `"text"`, `"json_object"`, or
    a full JSON schema dict. Not every vendor supports every shape.
    """
    messages: list[Message]
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[list[str]] = None
    seed: Optional[int] = None
    response_format: Union[str, dict, None] = None
    tools: Optional[list[FunctionTool]] = None
    server_tools: Optional[list[ServerTool]] = None
    tool_choice: Optional[ToolChoice] = None


StopReason = Literal["stop", "length", "tool_calls", "content_filter", "error"]


@dataclass
class ToolCall:
    """A function tool call emitted by the model in a non-streaming response."""
    call_id: str
    name: str
    arguments: str  # JSON string


@dataclass
class ChatResponse:
    """The result of a non-streaming chat completion."""
    content: str
    usage: Usage
    stop_reason: StopReason = "stop"
    model: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    metadata: Optional[dict] = None


# ---------------------------------------------------------------------------
# StreamEvent — 9-variant discriminated union
# ---------------------------------------------------------------------------


@dataclass
class StreamStart:
    """Emitted once at the start of a stream. Optional — not every vendor
    surfaces a start event (xAI doesn't, Anthropic does)."""
    model: Optional[str] = None
    stream_id: Optional[str] = None
    type: Literal["start"] = "start"


@dataclass
class ContentDelta:
    """A fragment of assistant text content."""
    text: str = ""
    type: Literal["content_delta"] = "content_delta"


@dataclass
class ReasoningDelta:
    """A fragment of model reasoning (chain-of-thought) content.

    Separate from ContentDelta because reasoning is usually surfaced
    differently in the UI and billed differently. Not every vendor streams
    reasoning as deltas — xAI tracks reasoning_tokens but doesn't yield them.
    """
    text: str = ""
    type: Literal["reasoning_delta"] = "reasoning_delta"


@dataclass
class FunctionToolCall:
    """Model is requesting execution of a client-side function tool.

    `arguments` may be a partial JSON string during streaming; callers
    should buffer until the stream ends before parsing.
    """
    call_id: str = ""
    name: str = ""
    arguments: str = ""  # JSON string, possibly partial
    type: Literal["function_tool_call"] = "function_tool_call"


@dataclass
class ServerToolAnnounce:
    """A server-side tool has started executing. Used for UI indicators
    ("searching the web...")."""
    tool_name: str = ""
    source: Optional[dict] = None  # e.g. {"query": "...", "url": "..."}
    type: Literal["server_tool_announce"] = "server_tool_announce"


@dataclass
class ServerToolResult:
    """A server-side tool has finished executing. `data` is a
    vendor-specific payload (citations, search hits, tool output)."""
    tool_name: str = ""
    data: list[dict] = field(default_factory=list)
    type: Literal["server_tool_result"] = "server_tool_result"


@dataclass
class UsageEvent:
    """A usage report. May be partial (mid-stream estimate) or final."""
    usage: Optional[Usage] = None
    partial: bool = False
    type: Literal["usage"] = "usage"


@dataclass
class StreamEnd:
    """Terminal event — the stream completed normally.

    `stop_reason` explains why the model stopped. Consumers should treat
    either `StreamEnd` *or* `StreamError` as the end of the stream; the
    two are mutually exclusive (a stream never yields both)."""
    stop_reason: StopReason = "stop"
    usage: Optional[Usage] = None
    type: Literal["end"] = "end"


@dataclass
class StreamError:
    """Terminal error event — the stream aborted with an error.

    `recoverable` hints whether the caller might retry (e.g. rate-limited)
    or should surface the error to the user. `StreamError` is terminal:
    consumers MUST treat it as end-of-stream and will NOT receive a
    subsequent `StreamEnd`. Cleanup logic should run on either
    `StreamEnd` *or* `StreamError`, never assume both."""
    message: str = ""
    recoverable: bool = False
    type: Literal["error"] = "error"


StreamEvent = Union[
    StreamStart,
    ContentDelta,
    ReasoningDelta,
    FunctionToolCall,
    ServerToolAnnounce,
    ServerToolResult,
    UsageEvent,
    StreamEnd,
    StreamError,
]


# ---------------------------------------------------------------------------
# LLMClient Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """Vendor-agnostic chat completion client.

    Concrete implementations wrap a specific vendor SDK (xAI, OpenAI,
    Anthropic, llama-server, ...) and translate its native shapes onto the
    canonical dataclasses in this module.

    Consumers should depend on this Protocol, not on any concrete
    implementation — that is what makes vendor swaps a wiring change rather
    than a source-code rewrite.
    """

    max_context: int
    """Maximum total tokens (input + output) this client's model will accept."""

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Run a non-streaming chat completion. Raises on error."""
        ...

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Run a streaming chat completion. The returned async iterator
        yields canonical StreamEvent variants until a terminal event
        (StreamEnd or StreamError)."""
        ...

    def supports(self, capability: str) -> bool:
        """Return True if this client supports the given capability.

        Canonical capability strings:
            "function_tools"          — client-side JSON-schema tool calls
            "server_tool:<name>"      — vendor-hosted tool (e.g.
                                        "server_tool:web_search")
            "json_mode"               — response_format="json_object"
            "json_schema"             — response_format with full schema
            "reasoning_tokens"        — reasoning_tokens in Usage
            "reasoning_stream"        — ReasoningDelta events in the stream
            "vision"                  — ImagePart in message content
            "streaming"               — stream_chat is meaningful (not
                                        simulated by collecting a full
                                        response and chunking it)
        """
        ...
