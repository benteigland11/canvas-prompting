from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Union


VALID_MESSAGE_ROLES = frozenset(
    {
        "system",
        "developer",
        "user",
        "assistant",
        "tool",
    }
)


@dataclass(frozen=True)
class LLMContextToolCall:
    """Provider-neutral tool call carried by an assistant message.

    Arguments are kept as a JSON-encoded string rather than a parsed dict
    because providers stream them character-by-character and partial JSON
    is common. Consumers parse at the boundary when they know the call is
    complete.
    """

    id: str
    name: str
    arguments: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("tool_call id must not be empty")
        if not self.name.strip():
            raise ValueError("tool_call name must not be empty")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class LLMContextTextPart:
    """A text fragment inside a multimodal message.

    Multimodal messages carry a list of content parts rather than a single
    string. Text parts are used to intersperse prose with images or other
    modalities in a single turn. Providers serialize these to their own
    content-array shapes (OpenAI-style `{"type": "text", "text": ...}`
    is the most common).
    """

    text: str

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("LLMContextTextPart.text must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text}


@dataclass(frozen=True)
class LLMContextImagePart:
    """An image reference inside a multimodal message.

    `image_url` may be either a plain string URL (including data: URLs for
    inline base64 images) or a dict with at least a ``url`` key plus any
    provider-specific hints (e.g. ``{"url": ..., "detail": "auto"}`` for
    OpenAI/xAI). Callers pass whichever shape they already have; the
    adapter decides how to render it for a given vendor.
    """

    image_url: Union[str, dict[str, Any]]

    def __post_init__(self) -> None:
        if isinstance(self.image_url, str):
            if not self.image_url.strip():
                raise ValueError("LLMContextImagePart.image_url must not be empty")
        elif isinstance(self.image_url, dict):
            if not self.image_url.get("url"):
                raise ValueError(
                    "LLMContextImagePart.image_url dict must contain a non-empty 'url' key"
                )
        else:
            raise ValueError(
                "LLMContextImagePart.image_url must be a string or a dict with a 'url' key"
            )

    def to_dict(self) -> dict[str, Any]:
        if isinstance(self.image_url, str):
            return {"type": "image_url", "image_url": {"url": self.image_url}}
        return {"type": "image_url", "image_url": dict(self.image_url)}


# Union of all content-part types a multimodal message may carry. New part
# types added in future versions (e.g. LLMContextAudioPart) should extend
# this alias.
LLMContextContentPart = Union[LLMContextTextPart, LLMContextImagePart]


@dataclass(frozen=True)
class LLMContextMessage:
    """Provider-neutral chat message carried in an LLM bundle.

    `content` may be a plain string (the common case for text-only turns)
    or a tuple of content parts for multimodal turns. List input is
    accepted by the constructor and normalized to a tuple for
    immutability.
    """

    role: str
    content: Union[str, tuple[LLMContextContentPart, ...]] = ""
    name: str = ""
    tool_call_id: str = ""
    tool_calls: tuple[LLMContextToolCall, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_role = self.role.strip().lower()
        if not normalized_role:
            raise ValueError("message role must not be empty")
        if normalized_role not in VALID_MESSAGE_ROLES:
            raise ValueError(f"unsupported message role '{self.role}'")

        # Normalize list content to a tuple so the dataclass stays immutable.
        if isinstance(self.content, list):
            object.__setattr__(self, "content", tuple(self.content))

        # Validate content part types if multimodal.
        if isinstance(self.content, tuple):
            for part in self.content:
                if not isinstance(part, (LLMContextTextPart, LLMContextImagePart)):
                    raise ValueError(
                        "multimodal content parts must be LLMContextTextPart "
                        f"or LLMContextImagePart, got {type(part).__name__}"
                    )

        # tool_calls is only meaningful on assistant turns — a provider
        # would never attach tool calls to a user or tool message.
        if self.tool_calls and normalized_role != "assistant":
            raise ValueError("tool_calls may only appear on assistant messages")

        # tool_call_id pairs a tool-result message with the assistant's
        # original call, so it only belongs on role=="tool".
        if self.tool_call_id and normalized_role != "tool":
            raise ValueError("tool_call_id may only appear on tool messages")

        # Empty content is allowed only for assistant messages whose whole
        # payload is tool_calls — a legitimate shape that providers emit
        # when the model decides to call a tool without speaking.
        is_empty = (
            not self.content.strip() if isinstance(self.content, str)
            else len(self.content) == 0
        )
        if is_empty:
            if not (normalized_role == "assistant" and self.tool_calls):
                raise ValueError(
                    "message content must not be empty "
                    "(only allowed for assistant messages that carry tool_calls)"
                )

        object.__setattr__(self, "role", normalized_role)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "role": self.role,
        }
        if isinstance(self.content, str):
            payload["content"] = self.content
        else:
            payload["content"] = [part.to_dict() for part in self.content]
        if self.name:
            payload["name"] = self.name
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            payload["tool_calls"] = [call.to_dict() for call in self.tool_calls]
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class LLMContextFunctionTool:
    """A tool the app defines and handles.

    The model emits a tool_call, the app executes, and the app returns a
    tool-role message with the result. Parameters are a JSON schema the
    provider will enforce on the model's output.
    """

    tool_id: str
    display_name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("tool_id must not be empty")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if not self.description.strip():
            raise ValueError("description must not be empty")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_id": self.tool_id,
            "display_name": self.display_name,
            "description": self.description,
        }
        if self.parameters:
            payload["parameters"] = dict(self.parameters)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


# Backwards-compat alias. v1.0 shipped a single LLMContextTool that matched
# what we now call a function tool. Keep the old name pointing at the new
# type so existing consumers and tests continue to work.
LLMContextTool = LLMContextFunctionTool


@dataclass(frozen=True)
class LLMContextServerTool:
    """A vendor-hosted tool the model invokes on its own.

    The app never sees the call happen — the provider runs the tool
    server-side and streams results back inline. Examples: xAI's
    web_search and x_search, Anthropic's computer_use. config is a
    vendor-specific opaque dict (e.g. {"max_results": 5}).
    """

    tool_id: str
    display_name: str
    description: str
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("tool_id must not be empty")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if not self.description.strip():
            raise ValueError("description must not be empty")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_id": self.tool_id,
            "display_name": self.display_name,
            "description": self.description,
        }
        if self.config:
            payload["config"] = dict(self.config)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class LLMContextBundle:
    """Canonical internal LLM input bundle before provider adaptation."""

    system_prompt: str = ""
    messages: tuple[LLMContextMessage, ...] = ()
    function_tools: tuple[LLMContextFunctionTool, ...] = ()
    server_tools: tuple[LLMContextServerTool, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tools(self) -> tuple[LLMContextFunctionTool, ...]:
        """Backwards-compat alias for function_tools.

        v1.0 exposed a single `tools` field. Existing consumers that only
        defined function tools still work via this alias — new consumers
        should use `function_tools` and `server_tools` directly.
        """
        return self.function_tools

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "system_prompt": self.system_prompt,
            "messages": [message.to_dict() for message in self.messages],
            "function_tools": [tool.to_dict() for tool in self.function_tools],
            "server_tools": [tool.to_dict() for tool in self.server_tools],
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class LLMContextBundleBuilder:
    """Mutable helper for assembling a canonical LLM context bundle."""

    def __init__(self) -> None:
        self._system_prompt = ""
        self._messages: list[LLMContextMessage] = []
        self._function_tools: list[LLMContextFunctionTool] = []
        self._server_tools: list[LLMContextServerTool] = []
        self._metadata: dict[str, Any] = {}

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt.strip()

    def add_message(
        self,
        *,
        role: str,
        content: Union[
            str,
            list[LLMContextContentPart],
            tuple[LLMContextContentPart, ...],
        ] = "",
        name: str = "",
        tool_call_id: str = "",
        tool_calls: tuple[LLMContextToolCall, ...] | list[LLMContextToolCall] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMContextMessage:
        message = LLMContextMessage(
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            tool_calls=tuple(tool_calls or ()),
            metadata=metadata or {},
        )
        self._messages.append(message)
        return message

    def add_multimodal_message(
        self,
        *,
        role: str,
        parts: list[LLMContextContentPart] | tuple[LLMContextContentPart, ...],
        metadata: dict[str, Any] | None = None,
    ) -> LLMContextMessage:
        """Convenience for a turn whose content is a list of parts
        (text + images). Equivalent to ``add_message(role=..., content=parts)``
        but makes the intent explicit at the call site."""
        return self.add_message(
            role=role,
            content=tuple(parts),
            metadata=metadata,
        )

    def add_assistant_tool_call_message(
        self,
        *,
        tool_calls: tuple[LLMContextToolCall, ...] | list[LLMContextToolCall],
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LLMContextMessage:
        """Convenience for the common shape: assistant turn that calls
        tools, optionally with accompanying text."""
        return self.add_message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            metadata=metadata,
        )

    def add_tool_result_message(
        self,
        *,
        tool_call_id: str,
        content: str,
        name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LLMContextMessage:
        """Convenience for a tool-role message responding to a prior
        assistant tool_call."""
        return self.add_message(
            role="tool",
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            metadata=metadata,
        )

    def extend_messages(self, messages: tuple[LLMContextMessage, ...] | list[LLMContextMessage]) -> None:
        self._messages.extend(messages)

    def add_function_tool(
        self,
        *,
        tool_id: str,
        display_name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMContextFunctionTool:
        tool = LLMContextFunctionTool(
            tool_id=tool_id,
            display_name=display_name,
            description=description,
            parameters=parameters or {},
            metadata=metadata or {},
        )
        self._function_tools.append(tool)
        return tool

    # Backwards-compat alias. v1.0 callers used `add_tool` to add what we
    # now call a function tool. Route it to the new storage so existing
    # code keeps working.
    add_tool = add_function_tool

    def add_server_tool(
        self,
        *,
        tool_id: str,
        display_name: str,
        description: str,
        config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMContextServerTool:
        tool = LLMContextServerTool(
            tool_id=tool_id,
            display_name=display_name,
            description=description,
            config=config or {},
            metadata=metadata or {},
        )
        self._server_tools.append(tool)
        return tool

    def extend_function_tools(
        self,
        tools: tuple[LLMContextFunctionTool, ...] | list[LLMContextFunctionTool],
    ) -> None:
        self._function_tools.extend(tools)

    def extend_server_tools(
        self,
        tools: tuple[LLMContextServerTool, ...] | list[LLMContextServerTool],
    ) -> None:
        self._server_tools.extend(tools)

    # Backwards-compat alias for the v1.0 extend_tools method.
    def extend_tools(
        self,
        tools: tuple[LLMContextFunctionTool, ...] | list[LLMContextFunctionTool],
    ) -> None:
        self._function_tools.extend(tools)

    def set_metadata(self, **metadata: Any) -> None:
        self._metadata.update(metadata)

    def build(self) -> LLMContextBundle:
        return LLMContextBundle(
            system_prompt=self._system_prompt,
            messages=tuple(self._messages),
            function_tools=tuple(self._function_tools),
            server_tools=tuple(self._server_tools),
            metadata=dict(self._metadata),
        )


def build_context_bundle(
    *,
    system_prompt: str = "",
    messages: tuple[LLMContextMessage, ...] | list[LLMContextMessage] = (),
    function_tools: tuple[LLMContextFunctionTool, ...] | list[LLMContextFunctionTool] = (),
    server_tools: tuple[LLMContextServerTool, ...] | list[LLMContextServerTool] = (),
    tools: tuple[LLMContextFunctionTool, ...] | list[LLMContextFunctionTool] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LLMContextBundle:
    """Build a bundle directly from immutable pieces.

    The ``tools`` kwarg is a backwards-compat alias that routes into
    ``function_tools`` — new code should pass ``function_tools`` and
    ``server_tools`` explicitly.
    """

    combined_function_tools: tuple[LLMContextFunctionTool, ...] = tuple(function_tools)
    if tools is not None:
        combined_function_tools = combined_function_tools + tuple(tools)

    return LLMContextBundle(
        system_prompt=system_prompt.strip(),
        messages=tuple(messages),
        function_tools=combined_function_tools,
        server_tools=tuple(server_tools),
        metadata=metadata or {},
    )
