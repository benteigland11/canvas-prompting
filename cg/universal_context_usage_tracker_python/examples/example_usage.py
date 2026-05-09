from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.context_usage_tracker import ContextUsageTracker


@dataclass(frozen=True)
class Snapshot:
    used_tokens: int
    level: str = "normal"
    warning_text: str = ""


tracker = ContextUsageTracker(max_tokens=500_000, reserve_tokens=50_000)
estimate = tracker.update_estimate(Snapshot(125_000))
print(f"estimate {estimate.label} {estimate.source}")

actual = tracker.update_actual_usage({"input_tokens": 130_000})
print(f"actual {actual.label} {actual.source}")
