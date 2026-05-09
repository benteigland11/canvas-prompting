from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent_compaction_summary import CompactionSummarySource
from src.agent_compaction_summary import build_compaction_summary_prompt
from src.agent_compaction_summary import build_compaction_summary_record


prompt = build_compaction_summary_prompt(
    (
        CompactionSummarySource(
            source_id="msg_1",
            source_type="message",
            text="The user wants the next turn to preserve decisions and open tasks.",
        ),
    ),
    window_state={"phase": "closing", "used_tokens": 360000, "max_tokens": 400000},
)
record = build_compaction_summary_record(
    summary_text="Preserve decisions and open tasks.",
    model="example-small-model",
    input_tokens_before=360000,
    output_tokens_after=1200,
)

print(prompt.splitlines()[0])
print(record.to_dict()["strategy"])
