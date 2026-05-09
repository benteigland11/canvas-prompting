from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from context_usage_tracker import ContextUsageTracker


@dataclass(frozen=True)
class Snapshot:
    used_tokens: int
    level: str = "normal"
    warning_text: str = ""


def test_context_usage_tracker_tracks_estimated_snapshot() -> None:
    tracker = ContextUsageTracker(max_tokens=500_000, reserve_tokens=50_000)

    state = tracker.update_estimate(Snapshot(125_000))

    assert state.used_tokens == 125_000
    assert state.max_tokens == 500_000
    assert state.usable_tokens == 450_000
    assert state.source == "estimated"
    assert state.label == "125K/500K"
    assert state.level == "normal"


def test_context_usage_tracker_prefers_actual_usage() -> None:
    tracker = ContextUsageTracker(max_tokens=100_000, reserve_tokens=10_000)
    tracker.update_estimate(Snapshot(1_000))

    state = tracker.update_actual_usage({"input_tokens": 80_000, "total_tokens": 90_000})

    assert state.used_tokens == 80_000
    assert state.source == "actual"
    assert state.level == "critical"
    assert state.warning_text == "Context nearly full (80000/90000)"
    assert tracker.last_actual_input_tokens() == 80_000


def test_context_usage_tracker_tracks_tokenized_usage() -> None:
    tracker = ContextUsageTracker(max_tokens=100_000, reserve_tokens=10_000)

    state = tracker.update_tokenized_usage(75_000)

    assert state.used_tokens == 75_000
    assert state.source == "tokenized"
    assert state.level == "warning"
    assert state.warning_text == "Context getting full (75000/90000 xAI)"


def test_context_usage_tracker_ignores_missing_actual_usage() -> None:
    tracker = ContextUsageTracker(max_tokens=100_000)
    estimated = tracker.update_estimate(Snapshot(2_000))

    state = tracker.update_actual_usage({})

    assert state == estimated


def test_context_usage_tracker_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="positive"):
        ContextUsageTracker(max_tokens=0)
    with pytest.raises(ValueError, match="smaller"):
        ContextUsageTracker(max_tokens=10, reserve_tokens=10)


def test_context_usage_tracker_formats_million_token_caps() -> None:
    tracker = ContextUsageTracker(max_tokens=1_500_000, reserve_tokens=100_000)

    state = tracker.update_estimate(Snapshot(1_250_000))

    assert state.label == "1.2M/1.5M"


def test_context_usage_tracker_buffers_result_events_without_exact_tokenization() -> None:
    tracker = ContextUsageTracker(max_tokens=100_000, chars_per_token=4.0)

    event = tracker.record_result_event(
        source_id="tool_runner",
        result_name="search",
        status="success",
        result={"items": ["alpha", "beta"]},
        turn_index=2,
        metadata={"request_id": "req_1"},
    )

    assert event.sequence == 1
    assert event.source_id == "tool_runner"
    assert event.result_name == "search"
    assert event.turn_index == 2
    assert event.estimated_tokens > 0
    assert event.exact_tokens is None
    assert event.needs_tokenization is True
    assert tracker.pending_tokenization_events() == (event,)
    assert tracker.result_ledger_summary().pending_tokenization_count == 1


def test_context_usage_tracker_marks_buffered_result_tokenized_later() -> None:
    tracker = ContextUsageTracker(max_tokens=100_000)
    event = tracker.record_result_event(
        source_id="tool_runner",
        result_name="read_file",
        status="success",
        result="hello world",
    )

    updated = tracker.mark_result_tokenized(event.sequence, 2)

    assert updated.exact_tokens == 2
    assert updated.token_count == 2
    assert updated.needs_tokenization is False
    assert tracker.pending_tokenization_events() == ()
    assert tracker.result_ledger_summary().total_tokens == 2


def test_context_usage_tracker_snapshot_restores_state_and_ledger() -> None:
    tracker = ContextUsageTracker(max_tokens=100_000, reserve_tokens=10_000)
    tracker.update_actual_usage({"input_tokens": 42})
    event = tracker.record_result_event(
        source_id="tool_runner",
        result_name="read_file",
        status="success",
        result="payload",
    )
    tracker.mark_result_tokenized(event.sequence, 1)

    restored = ContextUsageTracker(max_tokens=100_000, reserve_tokens=10_000)
    restored.restore_snapshot(tracker.snapshot())

    assert restored.state().used_tokens == 42
    assert restored.state().source == "actual"
    assert restored.last_actual_input_tokens() == 42
    assert len(restored.result_events()) == 1
    assert restored.result_events()[0].exact_tokens == 1
