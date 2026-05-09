from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Sequence


@dataclass(frozen=True)
class ToolRequest:
    """Single tool request emitted by the model."""

    request_id: str
    tool_name: str
    payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Single tool result returned by the runtime."""

    request_id: str
    tool_name: str
    status: str
    output: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelTurn:
    """Normalized model output for one loop iteration."""

    content: str = ""
    tool_requests: tuple[ToolRequest, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolLoopIteration:
    """Recorded tool loop iteration."""

    index: int
    model_turn: ModelTurn | None = None
    tool_results: tuple[ToolResult, ...] = ()


@dataclass(frozen=True)
class ToolLoopConfig:
    """Loop policy."""

    max_iterations: int = 8
    continue_on_tool_failure: bool = False
    max_duplicate_model_turns: int = 0
    max_duplicate_tool_request_attempts: int = 0
    max_repeated_tool_failures: int = 0
    require_progress: bool = False


@dataclass(frozen=True)
class ToolLoopDecision:
    """Next action for the caller to perform."""

    kind: str
    reason: str = ""
    iteration_index: int = 0
    model_turn: ModelTurn | None = None
    tool_requests: tuple[ToolRequest, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    final_content: str = ""


class AgentToolLoop:
    """Headless controller for model -> tool -> model continuation loops."""

    def __init__(self, config: ToolLoopConfig | None = None) -> None:
        self._config = config or ToolLoopConfig()
        self._iterations: list[ToolLoopIteration] = []
        self._awaiting_tool_results = False

    def reset(self) -> None:
        self._iterations.clear()
        self._awaiting_tool_results = False

    def iterations(self) -> tuple[ToolLoopIteration, ...]:
        return tuple(self._iterations)

    def current_iteration_index(self) -> int:
        return len(self._iterations)

    def begin(self) -> ToolLoopDecision:
        return ToolLoopDecision(
            kind="request_model",
            reason="begin_loop",
            iteration_index=self.current_iteration_index(),
        )

    def receive_model_turn(self, model_turn: ModelTurn) -> ToolLoopDecision:
        if self._awaiting_tool_results:
            raise RuntimeError("Cannot accept a new model turn while awaiting tool results")

        iteration_index = self.current_iteration_index()
        if iteration_index >= self._config.max_iterations:
            return ToolLoopDecision(
                kind="halt",
                reason="max_iterations_exceeded",
                iteration_index=iteration_index,
                model_turn=model_turn,
                final_content=model_turn.content,
            )

        if self._config.require_progress and not model_turn.content.strip() and not model_turn.tool_requests:
            return ToolLoopDecision(
                kind="halt",
                reason="no_progress_model_turn",
                iteration_index=iteration_index,
                model_turn=model_turn,
                final_content="Model returned no content and no tool action.",
            )

        duplicate_turn_halt = self._check_duplicate_model_turn(model_turn, iteration_index)
        if duplicate_turn_halt is not None:
            return duplicate_turn_halt
        duplicate_request_halt = self._check_duplicate_tool_request(model_turn, iteration_index)
        if duplicate_request_halt is not None:
            return duplicate_request_halt

        self._iterations.append(ToolLoopIteration(index=iteration_index, model_turn=model_turn))

        if model_turn.tool_requests:
            self._awaiting_tool_results = True
            return ToolLoopDecision(
                kind="execute_tools",
                reason="model_requested_tools",
                iteration_index=iteration_index,
                model_turn=model_turn,
                tool_requests=model_turn.tool_requests,
            )

        return ToolLoopDecision(
            kind="complete",
            reason="model_returned_final_content",
            iteration_index=iteration_index,
            model_turn=model_turn,
            final_content=model_turn.content,
        )

    def _check_duplicate_model_turn(
        self, model_turn: ModelTurn, iteration_index: int
    ) -> ToolLoopDecision | None:
        limit = self._config.max_duplicate_model_turns
        if limit <= 0 or not self._iterations:
            return None
        current_sig = self._model_turn_signature(model_turn)
        streak = 0
        for past in reversed(self._iterations):
            if past.model_turn is None:
                break
            if self._model_turn_signature(past.model_turn) == current_sig:
                streak += 1
            else:
                break
        if streak >= limit:
            return ToolLoopDecision(
                kind="halt",
                reason="duplicate_model_turn",
                iteration_index=iteration_index,
                model_turn=model_turn,
                final_content="Model kept producing duplicate model turns.",
            )
        return None

    def _check_duplicate_tool_request(
        self, model_turn: ModelTurn, iteration_index: int
    ) -> ToolLoopDecision | None:
        limit = self._config.max_duplicate_tool_request_attempts
        if limit <= 0:
            return None
        if not model_turn.tool_requests:
            return None
        current_sig = self._tool_request_signature(model_turn.tool_requests)
        streak = 0
        for past in reversed(self._iterations):
            if past.model_turn is None or not past.model_turn.tool_requests:
                break
            if self._tool_request_signature(past.model_turn.tool_requests) == current_sig:
                streak += 1
            else:
                break
        if streak >= limit:
            return ToolLoopDecision(
                kind="halt",
                reason="duplicate_tool_request",
                iteration_index=iteration_index,
                model_turn=model_turn,
                final_content="Model kept repeating the same tool request.",
            )
        return None

    @staticmethod
    def _model_turn_signature(turn: ModelTurn) -> tuple:
        return (turn.content, tuple((r.tool_name, repr(r.payload)) for r in turn.tool_requests))

    @staticmethod
    def _tool_request_signature(requests) -> tuple:
        return tuple((r.tool_name, repr(r.payload)) for r in requests)

    def _check_repeated_tool_failure(
        self,
        results: tuple,
        iteration_index: int,
        model_turn: ModelTurn | None,
    ) -> ToolLoopDecision | None:
        limit = self._config.max_repeated_tool_failures
        if limit <= 0:
            return None
        failing = [result for result in results if result.status != "success"]
        if not failing:
            return None
        current_sig = tuple((r.tool_name, getattr(r, "error_code", ""), getattr(r, "error", "")) for r in failing)
        streak = 0
        for past in reversed(self._iterations[:-1]):
            past_failing = [r for r in past.tool_results if r.status != "success"]
            if not past_failing:
                break
            past_sig = tuple((r.tool_name, getattr(r, "error_code", ""), getattr(r, "error", "")) for r in past_failing)
            if past_sig == current_sig:
                streak += 1
            else:
                break
        if streak >= limit:
            return ToolLoopDecision(
                kind="halt",
                reason="repeated_tool_failure",
                iteration_index=iteration_index,
                model_turn=model_turn,
                tool_results=results,
                final_content="Same tool failure repeated past the configured limit.",
            )
        return None

    def receive_tool_results(self, results: Sequence[ToolResult]) -> ToolLoopDecision:
        if not self._awaiting_tool_results:
            raise RuntimeError("Cannot accept tool results before the model requests tools")
        if not self._iterations:
            raise RuntimeError("Cannot accept tool results without an active iteration")

        normalized_results = tuple(results)
        last_iteration = self._iterations[-1]
        self._iterations[-1] = ToolLoopIteration(
            index=last_iteration.index,
            model_turn=last_iteration.model_turn,
            tool_results=normalized_results,
        )
        self._awaiting_tool_results = False

        has_failures = any(result.status != "success" for result in normalized_results)
        if has_failures and not self._config.continue_on_tool_failure:
            return ToolLoopDecision(
                kind="halt",
                reason="tool_failure",
                iteration_index=last_iteration.index,
                model_turn=last_iteration.model_turn,
                tool_results=normalized_results,
            )

        repeat_fail_halt = self._check_repeated_tool_failure(
            normalized_results, last_iteration.index, last_iteration.model_turn
        )
        if repeat_fail_halt is not None:
            return repeat_fail_halt

        if len(self._iterations) >= self._config.max_iterations:
            return ToolLoopDecision(
                kind="halt",
                reason="max_iterations_reached_after_tools",
                iteration_index=last_iteration.index,
                model_turn=last_iteration.model_turn,
                tool_results=normalized_results,
            )

        reason = "tool_results_ready_after_failure" if has_failures else "tool_results_ready"
        return ToolLoopDecision(
            kind="request_model",
            reason=reason,
            iteration_index=self.current_iteration_index(),
            tool_results=normalized_results,
        )
