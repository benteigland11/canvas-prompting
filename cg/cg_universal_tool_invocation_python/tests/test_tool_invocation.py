from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tool_invocation import ToolInvocationRequest
from src.tool_invocation import ToolInvocationRouter
from src.tool_invocation import ToolInvocationTarget


def test_invoke_returns_unknown_for_missing_tool() -> None:
    router = ToolInvocationRouter()

    result = router.invoke(ToolInvocationRequest(tool_id="missing"))

    assert result.status == "unknown_tool"


def test_invoke_returns_permission_required_when_not_allowed() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="read_file",
                handler=lambda path: f"read {path}",
                permission_mode="ask",
            ),
        )
    )

    result = router.invoke(ToolInvocationRequest(tool_id="read_file", args=("README.md",)))

    assert result.status == "permission_required"
    assert result.permission_mode == "ask"


def test_invoke_runs_allowed_sync_tool() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="echo",
                handler=lambda text: f"echo:{text}",
                target_kind="mcp",
                source_id="search-server",
                display_name="Echo",
                permission_mode="allow",
                metadata={"category": "utility"},
            ),
        )
    )

    result = router.invoke(ToolInvocationRequest(tool_id="echo", args=("hello",)))

    assert result.status == "success"
    assert result.output == "echo:hello"
    assert result.target_kind == "mcp"
    assert result.source_id == "search-server"
    assert result.display_name == "Echo"
    assert result.metadata == {"category": "utility"}


def test_invoke_returns_async_required_for_async_tool_on_sync_path() -> None:
    async def async_tool(value: str) -> str:
        return value.upper()

    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="async_tool",
                handler=async_tool,
                permission_mode="allow",
            ),
        )
    )

    result = router.invoke(ToolInvocationRequest(tool_id="async_tool", args=("x",)))

    assert result.status == "async_required"


@pytest.mark.asyncio
async def test_invoke_async_runs_async_tool() -> None:
    async def async_tool(value: str) -> str:
        return value.upper()

    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="async_tool",
                handler=async_tool,
                permission_mode="allow",
            ),
        )
    )

    result = await router.invoke_async(ToolInvocationRequest(tool_id="async_tool", args=("x",)))

    assert result.status == "success"
    assert result.output == "X"


def test_invoke_captures_handler_errors() -> None:
    def boom() -> str:
        raise RuntimeError("bad")

    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="boom",
                handler=boom,
                permission_mode="allow",
            ),
        )
    )

    result = router.invoke(ToolInvocationRequest(tool_id="boom"))

    assert result.status == "error"
    assert "RuntimeError: bad" in result.error


def test_empty_scopes_target_is_universal_even_with_resolver() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="echo",
                handler=lambda: "ok",
                permission_mode="allow",
            ),
        )
    )
    router.set_scope_resolver(lambda: "focus")

    result = router.invoke(ToolInvocationRequest(tool_id="echo"))

    assert result.status == "success"


def test_invoke_out_of_scope_when_scope_mismatch() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="scratch",
                handler=lambda: "ok",
                permission_mode="allow",
                scopes=("overview",),
            ),
        )
    )
    router.set_scope_resolver(lambda: "focus")

    result = router.invoke(ToolInvocationRequest(tool_id="scratch"))

    assert result.status == "out_of_scope"
    assert "focus" in result.error


def test_invoke_in_scope_runs_normally() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="scratch",
                handler=lambda: "ok",
                permission_mode="allow",
                scopes=("overview",),
            ),
        )
    )
    router.set_scope_resolver(lambda: "overview")

    result = router.invoke(ToolInvocationRequest(tool_id="scratch"))

    assert result.status == "success"
    assert result.output == "ok"


def test_out_of_scope_takes_precedence_over_permission() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="scratch",
                handler=lambda: "ok",
                permission_mode="ask",
                scopes=("overview",),
            ),
        )
    )
    router.set_scope_resolver(lambda: "focus")

    result = router.invoke(ToolInvocationRequest(tool_id="scratch"))

    assert result.status == "out_of_scope"


def test_disabled_takes_precedence_over_out_of_scope() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="scratch",
                handler=lambda: "ok",
                permission_mode="allow",
                enabled=False,
                scopes=("overview",),
            ),
        )
    )
    router.set_scope_resolver(lambda: "focus")

    result = router.invoke(ToolInvocationRequest(tool_id="scratch"))

    assert result.status == "disabled"


def test_list_targets_in_scope_filters() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(tool_id="read", handler=lambda: None, permission_mode="allow"),
            ToolInvocationTarget(tool_id="scratch", handler=lambda: None, permission_mode="allow", scopes=("overview",)),
            ToolInvocationTarget(tool_id="edit", handler=lambda: None, permission_mode="allow", scopes=("focus",)),
        )
    )

    focus_ids = [t.tool_id for t in router.list_targets_in_scope("focus")]
    overview_ids = [t.tool_id for t in router.list_targets_in_scope("overview")]

    assert focus_ids == ["edit", "read"]
    assert overview_ids == ["read", "scratch"]


def test_list_current_targets_filters_by_current_scope() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(tool_id="read", handler=lambda: None, permission_mode="allow"),
            ToolInvocationTarget(tool_id="scratch", handler=lambda: None, permission_mode="allow", scopes=("overview",)),
            ToolInvocationTarget(tool_id="edit", handler=lambda: None, permission_mode="allow", scopes=("focus",)),
        )
    )
    router.set_scope_resolver(lambda: "focus")

    focus_ids = [t.tool_id for t in router.list_current_targets()]

    assert focus_ids == ["edit", "read"]


def test_list_current_targets_returns_all_without_resolver() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(tool_id="a", handler=lambda: None, scopes=("x",)),
            ToolInvocationTarget(tool_id="b", handler=lambda: None),
        )
    )

    ids = [t.tool_id for t in router.list_current_targets()]

    assert ids == ["a", "b"]


def test_current_scope_reads_resolver() -> None:
    router = ToolInvocationRouter()
    assert router.current_scope() == ""
    router.set_scope_resolver(lambda: "overview")
    assert router.current_scope() == "overview"
    router.set_scope_resolver(None)
    assert router.current_scope() == ""


@pytest.mark.asyncio
async def test_invoke_async_returns_out_of_scope() -> None:
    async def async_tool() -> str:
        return "ok"

    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="scratch",
                handler=async_tool,
                permission_mode="allow",
                scopes=("overview",),
            ),
        )
    )
    router.set_scope_resolver(lambda: "focus")

    result = await router.invoke_async(ToolInvocationRequest(tool_id="scratch"))

    assert result.status == "out_of_scope"


def test_permission_required_carries_target_identity() -> None:
    router = ToolInvocationRouter(
        (
            ToolInvocationTarget(
                tool_id="search_documents",
                handler=lambda query: query,
                target_kind="mcp",
                source_id="example-server",
                display_name="Search Documents",
                permission_mode="ask",
            ),
        )
    )

    result = router.invoke(ToolInvocationRequest(tool_id="search_documents", args=("widgets",)))

    assert result.status == "permission_required"
    assert result.target_kind == "mcp"
    assert result.source_id == "example-server"
    assert result.display_name == "Search Documents"
