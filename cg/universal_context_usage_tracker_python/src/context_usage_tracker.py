from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
from typing import Any
from typing import Literal


UsageSource = Literal["estimated", "tokenized", "actual"]


@dataclass(frozen=True)
class ContextUsageState:
    used_tokens: int
    max_tokens: int
    reserve_tokens: int
    usable_tokens: int
    fill_ratio: float
    level: str
    source: UsageSource
    label: str
    warning_text: str = ""


@dataclass(frozen=True)
class ContextResultEvent:
    """One context-producing result buffered for later exact tokenization."""

    sequence: int
    source_id: str
    result_name: str
    status: str
    source_text: str
    estimated_tokens: int
    exact_tokens: int | None = None
    turn_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return self.exact_tokens if self.exact_tokens is not None else self.estimated_tokens

    @property
    def needs_tokenization(self) -> bool:
        return self.exact_tokens is None


@dataclass(frozen=True)
class ContextResultLedgerSummary:
    event_count: int
    pending_tokenization_count: int
    estimated_tokens: int
    exact_tokens: int
    total_tokens: int


class ContextUsageTracker:
    """Track current context pressure from estimates and provider usage."""

    def __init__(self, *, max_tokens: int, reserve_tokens: int = 0, chars_per_token: float = 4.0) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if reserve_tokens < 0:
            raise ValueError("reserve_tokens must be non-negative")
        if reserve_tokens >= max_tokens:
            raise ValueError("reserve_tokens must be smaller than max_tokens")
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self._max_tokens = max_tokens
        self._reserve_tokens = reserve_tokens
        self._chars_per_token = float(chars_per_token)
        self._last_actual_input_tokens: int | None = None
        self._result_events: list[ContextResultEvent] = []
        self._next_result_sequence = 1
        self._state = _state(
            used_tokens=0,
            max_tokens=max_tokens,
            reserve_tokens=reserve_tokens,
            source="estimated",
            level="normal",
            warning_text="",
        )

    def update_estimate(self, snapshot: object) -> ContextUsageState:
        used_tokens = _non_negative_int(getattr(snapshot, "used_tokens", 0))
        level = str(getattr(snapshot, "level", "normal") or "normal")
        warning_text = str(getattr(snapshot, "warning_text", "") or "")
        self._state = _state(
            used_tokens=used_tokens,
            max_tokens=self._max_tokens,
            reserve_tokens=self._reserve_tokens,
            source="estimated",
            level=level,
            warning_text=warning_text,
        )
        return self._state

    def update_actual_usage(self, usage: dict[str, Any] | object | None) -> ContextUsageState:
        actual_input_tokens = _actual_input_tokens(usage)
        if actual_input_tokens is None:
            return self._state
        self._last_actual_input_tokens = actual_input_tokens
        self._state = _state(
            used_tokens=actual_input_tokens,
            max_tokens=self._max_tokens,
            reserve_tokens=self._reserve_tokens,
            source="actual",
            level=_level(actual_input_tokens, self._state.usable_tokens),
            warning_text=_warning_text(actual_input_tokens, self._state.usable_tokens, "actual"),
        )
        return self._state

    def update_tokenized_usage(self, token_count: int) -> ContextUsageState:
        used_tokens = _non_negative_int(token_count)
        self._state = _state(
            used_tokens=used_tokens,
            max_tokens=self._max_tokens,
            reserve_tokens=self._reserve_tokens,
            source="tokenized",
            level=_level(used_tokens, self._state.usable_tokens),
            warning_text=_warning_text(used_tokens, self._state.usable_tokens, "tokenized"),
        )
        return self._state

    def state(self) -> ContextUsageState:
        return self._state

    def last_actual_input_tokens(self) -> int | None:
        return self._last_actual_input_tokens

    def record_result_event(
        self,
        *,
        source_id: str,
        result_name: str,
        status: str,
        result: Any,
        turn_index: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContextResultEvent:
        """Buffer a context-producing result without making an external tokenizer call."""

        source_text = serialize_context_result(result)
        event = ContextResultEvent(
            sequence=self._next_result_sequence,
            source_id=str(source_id),
            result_name=str(result_name),
            status=str(status),
            source_text=source_text,
            estimated_tokens=_estimate_text_tokens(source_text, self._chars_per_token),
            turn_index=turn_index,
            metadata=dict(metadata or {}),
        )
        self._next_result_sequence += 1
        self._result_events.append(event)
        return event

    def result_events(self) -> tuple[ContextResultEvent, ...]:
        return tuple(self._result_events)

    def pending_tokenization_events(self) -> tuple[ContextResultEvent, ...]:
        return tuple(event for event in self._result_events if event.needs_tokenization)

    def mark_result_tokenized(self, sequence: int, token_count: int) -> ContextResultEvent:
        resolved_sequence = int(sequence)
        resolved_token_count = _non_negative_int(token_count)
        for index, event in enumerate(self._result_events):
            if event.sequence != resolved_sequence:
                continue
            updated = ContextResultEvent(
                sequence=event.sequence,
                source_id=event.source_id,
                result_name=event.result_name,
                status=event.status,
                source_text=event.source_text,
                estimated_tokens=event.estimated_tokens,
                exact_tokens=resolved_token_count,
                turn_index=event.turn_index,
                metadata=dict(event.metadata),
            )
            self._result_events[index] = updated
            return updated
        raise KeyError(f"Unknown context result event sequence: {sequence}")

    def result_ledger_summary(self) -> ContextResultLedgerSummary:
        estimated_tokens = sum(event.estimated_tokens for event in self._result_events)
        exact_tokens = sum(event.exact_tokens or 0 for event in self._result_events)
        total_tokens = sum(event.token_count for event in self._result_events)
        pending_count = sum(1 for event in self._result_events if event.needs_tokenization)
        return ContextResultLedgerSummary(
            event_count=len(self._result_events),
            pending_tokenization_count=pending_count,
            estimated_tokens=estimated_tokens,
            exact_tokens=exact_tokens,
            total_tokens=total_tokens,
        )

    def clear_result_events(self) -> None:
        self._result_events.clear()
        self._next_result_sequence = 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": {
                "used_tokens": self._state.used_tokens,
                "max_tokens": self._state.max_tokens,
                "reserve_tokens": self._state.reserve_tokens,
                "source": self._state.source,
                "level": self._state.level,
                "warning_text": self._state.warning_text,
            },
            "last_actual_input_tokens": self._last_actual_input_tokens,
            "chars_per_token": self._chars_per_token,
            "next_result_sequence": self._next_result_sequence,
            "result_events": [result_event_to_dict(event) for event in self._result_events],
        }

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        if not isinstance(snapshot, dict):
            return
        raw_state = dict(snapshot.get("state", {}) or {})
        used_tokens = _non_negative_int(raw_state.get("used_tokens", 0))
        source = str(raw_state.get("source", "estimated") or "estimated")
        if source not in {"estimated", "tokenized", "actual"}:
            source = "estimated"
        self._state = _state(
            used_tokens=used_tokens,
            max_tokens=self._max_tokens,
            reserve_tokens=self._reserve_tokens,
            source=source,  # type: ignore[arg-type]
            level=str(raw_state.get("level", "normal") or "normal"),
            warning_text=str(raw_state.get("warning_text", "") or ""),
        )
        self._last_actual_input_tokens = _optional_non_negative_int(snapshot.get("last_actual_input_tokens"))
        raw_events = snapshot.get("result_events", ())
        self._result_events = [
            result_event_from_dict(item)
            for item in raw_events
            if isinstance(item, dict)
        ]
        next_sequence = _optional_non_negative_int(snapshot.get("next_result_sequence"))
        minimum_next = max((event.sequence for event in self._result_events), default=0) + 1
        self._next_result_sequence = max(next_sequence or minimum_next, minimum_next)


def _state(
    *,
    used_tokens: int,
    max_tokens: int,
    reserve_tokens: int,
    source: UsageSource,
    level: str,
    warning_text: str,
) -> ContextUsageState:
    usable_tokens = max(1, max_tokens - reserve_tokens)
    fill_ratio = min(max(used_tokens / usable_tokens, 0.0), 1.0)
    resolved_level = _level(used_tokens, usable_tokens) if level == "normal" else level
    return ContextUsageState(
        used_tokens=used_tokens,
        max_tokens=max_tokens,
        reserve_tokens=reserve_tokens,
        usable_tokens=usable_tokens,
        fill_ratio=fill_ratio,
        level=resolved_level,
        source=source,
        label=f"{_compact(used_tokens)}/{_compact(max_tokens)}",
        warning_text=warning_text or _warning_text(used_tokens, usable_tokens, source),
    )


def _actual_input_tokens(usage: dict[str, Any] | object | None) -> int | None:
    if usage is None:
        return None
    if hasattr(usage, "as_dict"):
        usage = usage.as_dict()
    if not isinstance(usage, dict):
        usage = {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }
    for key in ("input_tokens", "prompt_tokens", "total_tokens"):
        value = _optional_non_negative_int(usage.get(key))
        if value is not None:
            return value
    return None


def _optional_non_negative_int(value: Any) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    return resolved if resolved >= 0 else None


def _non_negative_int(value: Any) -> int:
    resolved = _optional_non_negative_int(value)
    return resolved if resolved is not None else 0


def serialize_context_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, sort_keys=True, default=repr, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(result)


def _estimate_text_tokens(text: str, chars_per_token: float) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, int((len(stripped) + chars_per_token - 1) // chars_per_token))


def _level(used_tokens: int, usable_tokens: int) -> str:
    ratio = used_tokens / usable_tokens
    if used_tokens > usable_tokens:
        return "overflow"
    if ratio >= 0.85:
        return "critical"
    if ratio >= 0.7:
        return "warning"
    return "normal"


def _warning_text(used_tokens: int, usable_tokens: int, source: str) -> str:
    level = _level(used_tokens, usable_tokens)
    suffix = "" if source == "actual" else (" xAI" if source == "tokenized" else " est.")
    if level == "warning":
        return f"Context getting full ({used_tokens}/{usable_tokens}{suffix})"
    if level == "critical":
        return f"Context nearly full ({used_tokens}/{usable_tokens}{suffix})"
    if level == "overflow":
        return f"Context over budget ({used_tokens}/{usable_tokens}{suffix})"
    return ""


def _compact(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value // 1_000}K"
    return str(value)


def result_event_to_dict(event: ContextResultEvent) -> dict[str, Any]:
    return {
        "sequence": event.sequence,
        "source_id": event.source_id,
        "result_name": event.result_name,
        "status": event.status,
        "source_text": event.source_text,
        "estimated_tokens": event.estimated_tokens,
        "exact_tokens": event.exact_tokens,
        "turn_index": event.turn_index,
        "metadata": dict(event.metadata),
    }


def result_event_from_dict(payload: dict[str, Any]) -> ContextResultEvent:
    return ContextResultEvent(
        sequence=max(1, _non_negative_int(payload.get("sequence", 1))),
        source_id=str(payload.get("source_id", "") or ""),
        result_name=str(payload.get("result_name", "") or ""),
        status=str(payload.get("status", "") or ""),
        source_text=str(payload.get("source_text", "") or ""),
        estimated_tokens=_non_negative_int(payload.get("estimated_tokens", 0)),
        exact_tokens=_optional_non_negative_int(payload.get("exact_tokens")),
        turn_index=_optional_non_negative_int(payload.get("turn_index")),
        metadata=dict(payload.get("metadata", {}) or {}),
    )
