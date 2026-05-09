from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_context_window_policy import ContextWindowPolicyConfig
from agent_context_window_policy import WINDOW_CLOSING
from agent_context_window_policy import WINDOW_COMPACTED
from agent_context_window_policy import WINDOW_OPEN
from agent_context_window_policy import complete_context_window_compaction
from agent_context_window_policy import context_window_prompt_source_content
from agent_context_window_policy import evaluate_context_window


def test_context_window_is_open_below_closing_threshold() -> None:
    state = evaluate_context_window(
        used_tokens=359999,
        config=ContextWindowPolicyConfig(max_tokens=400000, closing_ratio=0.9),
    )

    assert state.phase == WINDOW_OPEN
    assert state.closing_tokens == 360000
    assert state.soft_stop_pending is False
    assert context_window_prompt_source_content(state) == ""


def test_context_window_closes_at_threshold() -> None:
    state = evaluate_context_window(
        used_tokens=360000,
        config=ContextWindowPolicyConfig(max_tokens=400000, closing_ratio=0.9),
    )

    assert state.phase == WINDOW_CLOSING
    assert state.soft_stop_pending is True
    assert "durable summary boundary" in state.prompt_guidance
    assert "360,000/400,000" in context_window_prompt_source_content(state)


def test_context_window_can_be_marked_compacted() -> None:
    closing = evaluate_context_window(
        used_tokens=380000,
        config=ContextWindowPolicyConfig(max_tokens=400000, closing_ratio=0.9),
    )

    compacted = complete_context_window_compaction(closing)

    assert compacted["phase"] == WINDOW_COMPACTED
    assert compacted["soft_stop_pending"] is False
    assert "stable pre-boundary" in compacted["prompt_guidance"]


def test_compacted_phase_stays_compacted() -> None:
    state = evaluate_context_window(
        used_tokens=1000,
        config=ContextWindowPolicyConfig(max_tokens=400000, closing_ratio=0.9),
        current_phase=WINDOW_COMPACTED,
    )

    assert state.phase == WINDOW_COMPACTED
