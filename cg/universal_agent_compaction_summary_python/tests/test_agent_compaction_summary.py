from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_compaction_summary import CompactionSummarySource
from agent_compaction_summary import build_compaction_summary_prompt
from agent_compaction_summary import build_compaction_summary_record


def test_build_compaction_summary_prompt_includes_sections_and_state() -> None:
    prompt = build_compaction_summary_prompt(
        (
            CompactionSummarySource(
                source_id="msg_1",
                source_type="message",
                text="User wants the next turn to preserve decisions.",
                token_count=12,
            ),
        ),
        window_state={"phase": "closing", "used_tokens": 360000, "max_tokens": 400000},
        day_phase={"phase": "afternoon"},
    )

    assert "Create a durable context-window handoff summary." in prompt
    assert "User goal and standing preferences" in prompt
    assert "phase: closing" in prompt
    assert "[message:msg_1]" in prompt


def test_build_compaction_summary_prompt_clips_sources() -> None:
    prompt = build_compaction_summary_prompt(
        ({"source_id": "tool_1", "source_type": "tool_result", "text": "x" * 3000},),
        max_source_chars=1200,
    )

    assert "[truncated]" in prompt
    assert len(prompt) < 1800


def test_build_compaction_summary_record_normalizes_ids_and_usage() -> None:
    record = build_compaction_summary_record(
        summary_text=" Keep this summary. ",
        model="small-model",
        input_tokens_before=1000,
        output_tokens_after=250,
        source_event_ids=("evt_1", "", "evt_2"),
        source_message_ids=("msg_1",),
        metadata={"phase": "closing"},
    )

    payload = record.to_dict()

    assert payload["compaction_id"].startswith("compact_")
    assert payload["summary_message_id"].startswith("msg_summary_")
    assert payload["summary_text"] == "Keep this summary."
    assert payload["input_tokens_before"] == 1000
    assert payload["output_tokens_after"] == 250
    assert payload["source_event_ids"] == ["evt_1", "evt_2"]
    assert payload["metadata"]["phase"] == "closing"
