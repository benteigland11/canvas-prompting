from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import inspect
from typing import Any
from typing import Awaitable
from typing import Callable


ToolHandler = Callable[..., Any]
AsyncToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolInvocationTarget:
    """Single invokable tool target."""

    tool_id: str
    handler: ToolHandler | AsyncToolHandler
    target_kind: str = "local"
    source_id: str = ""
    display_name: str = ""
    permission_mode: str = "ask"
    enabled: bool = True
    scopes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolInvocationRequest:
    """Requested tool call."""

    tool_id: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolInvocationResult:
    """Structured result of a tool invocation attempt."""

    status: str
    tool_id: str
    output: Any = None
    error: str = ""
    error_code: str = ""
    retryable: bool | None = None
    severity: str = ""
    permission_mode: str = "ask"
    target_kind: str = "local"
    source_id: str = ""
    display_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolInvocationRouter:
    """Headless tool invocation router with sync and async execution paths."""

    def __init__(self, targets: tuple[ToolInvocationTarget, ...] = ()) -> None:
        self._targets: dict[str, ToolInvocationTarget] = {target.tool_id: target for target in targets}
        self._scope_resolver: Callable[[], str] | None = None

    def register(self, target: ToolInvocationTarget) -> None:
        self._targets[target.tool_id] = target

    def get(self, tool_id: str) -> ToolInvocationTarget | None:
        return self._targets.get(tool_id)

    def list_targets(self) -> tuple[ToolInvocationTarget, ...]:
        return tuple(sorted(self._targets.values(), key=lambda target: target.tool_id))

    def set_scope_resolver(self, resolver: Callable[[], str] | None) -> None:
        """Install a callable that returns the currently active scope name.

        When set, `invoke` returns status `"out_of_scope"` for any target whose
        `scopes` tuple is non-empty and does not contain the current scope.
        Targets with empty `scopes` are universal and always in scope.
        Pass `None` to remove the resolver (all targets become universal).
        """

        self._scope_resolver = resolver

    def current_scope(self) -> str:
        """Return the current scope from the resolver, or empty string if unset."""

        if self._scope_resolver is None:
            return ""
        return self._scope_resolver()

    def is_target_in_scope(self, target: ToolInvocationTarget, scope: str) -> bool:
        if not target.scopes:
            return True
        return scope in target.scopes

    def list_targets_in_scope(self, scope: str) -> tuple[ToolInvocationTarget, ...]:
        return tuple(
            sorted(
                (t for t in self._targets.values() if self.is_target_in_scope(t, scope)),
                key=lambda target: target.tool_id,
            )
        )

    def list_current_targets(self) -> tuple[ToolInvocationTarget, ...]:
        """Return targets in the current scope.

        Sugar for ``list_targets_in_scope(current_scope())``. When no scope
        resolver is installed this is equivalent to ``list_targets()``.
        """

        if self._scope_resolver is None:
            return self.list_targets()
        return self.list_targets_in_scope(self._scope_resolver())

    def invoke(self, request: ToolInvocationRequest) -> ToolInvocationResult:
        """Invoke a tool request synchronously."""

        target = self._targets.get(request.tool_id)
        if target is None:
            return ToolInvocationResult(
                status="unknown_tool",
                tool_id=request.tool_id,
                error=f"Unknown tool: {request.tool_id}",
                error_code="unknown_tool",
                retryable=False,
                severity="error",
            )
        if not target.enabled:
            return _result_from_target(
                target,
                status="disabled",
                tool_id=request.tool_id,
                error=f"Tool disabled: {request.tool_id}",
            )
        if self._scope_resolver is not None and target.scopes:
            scope = self._scope_resolver()
            if scope not in target.scopes:
                return _result_from_target(
                    target,
                    status="out_of_scope",
                    tool_id=request.tool_id,
                    error=f"Tool '{request.tool_id}' is not available in scope '{scope}'",
                    error_code="out_of_scope",
                    retryable=False,
                    severity="warning",
                )
        if target.permission_mode != "allow":
            return _result_from_target(
                target,
                status="permission_required",
                tool_id=request.tool_id,
                error_code="permission_required",
                retryable=True,
                severity="warning",
            )
        if inspect.iscoroutinefunction(target.handler):
            return _result_from_target(
                target,
                status="async_required",
                tool_id=request.tool_id,
                error=f"Tool '{request.tool_id}' requires async invocation",
                error_code="async_required",
                retryable=True,
                severity="error",
            )
        try:
            output = target.handler(*request.args, **request.kwargs)
        except Exception as exc:
            error_text = str(exc).strip() or f"{type(exc).__name__}: invocation failed"
            if not getattr(exc, "error_code", "") and not error_text.startswith(f"{type(exc).__name__}:"):
                error_text = f"{type(exc).__name__}: {error_text}"
            return _result_from_target(
                target,
                status="error",
                tool_id=request.tool_id,
                error=error_text,
                error_code=str(getattr(exc, "error_code", "")),
                retryable=getattr(exc, "retryable", None),
                severity=str(getattr(exc, "severity", "")),
            )
        return _result_from_target(
            target,
            status="success",
            tool_id=request.tool_id,
            output=output,
        )

    async def invoke_async(self, request: ToolInvocationRequest) -> ToolInvocationResult:
        """Invoke a tool request with async handler support."""

        target = self._targets.get(request.tool_id)
        if target is None:
            return ToolInvocationResult(
                status="unknown_tool",
                tool_id=request.tool_id,
                error=f"Unknown tool: {request.tool_id}",
                error_code="unknown_tool",
                retryable=False,
                severity="error",
            )
        if not target.enabled:
            return _result_from_target(
                target,
                status="disabled",
                tool_id=request.tool_id,
                error=f"Tool disabled: {request.tool_id}",
            )
        if self._scope_resolver is not None and target.scopes:
            scope = self._scope_resolver()
            if scope not in target.scopes:
                return _result_from_target(
                    target,
                    status="out_of_scope",
                    tool_id=request.tool_id,
                    error=f"Tool '{request.tool_id}' is not available in scope '{scope}'",
                    error_code="out_of_scope",
                    retryable=False,
                    severity="warning",
                )
        if target.permission_mode != "allow":
            return _result_from_target(
                target,
                status="permission_required",
                tool_id=request.tool_id,
                error_code="permission_required",
                retryable=True,
                severity="warning",
            )
        try:
            if inspect.iscoroutinefunction(target.handler):
                output = await target.handler(*request.args, **request.kwargs)
            else:
                output = target.handler(*request.args, **request.kwargs)
        except Exception as exc:
            error_text = str(exc).strip() or f"{type(exc).__name__}: invocation failed"
            if not getattr(exc, "error_code", "") and not error_text.startswith(f"{type(exc).__name__}:"):
                error_text = f"{type(exc).__name__}: {error_text}"
            return _result_from_target(
                target,
                status="error",
                tool_id=request.tool_id,
                error=error_text,
                error_code=str(getattr(exc, "error_code", "")),
                retryable=getattr(exc, "retryable", None),
                severity=str(getattr(exc, "severity", "")),
            )
        return _result_from_target(
            target,
            status="success",
            tool_id=request.tool_id,
            output=output,
        )


def _result_from_target(
    target: ToolInvocationTarget,
    *,
    status: str,
    tool_id: str,
    output: Any = None,
    error: str = "",
    error_code: str = "",
    retryable: bool | None = None,
    severity: str = "",
) -> ToolInvocationResult:
    return ToolInvocationResult(
        status=status,
        tool_id=tool_id,
        output=output,
        error=error,
        error_code=error_code,
        retryable=retryable,
        severity=severity,
        permission_mode=target.permission_mode,
        target_kind=target.target_kind,
        source_id=target.source_id,
        display_name=target.display_name or target.tool_id,
        metadata=dict(target.metadata),
    )
