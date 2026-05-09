from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.context_optimization_report import format_context_optimization_report


view = format_context_optimization_report(
    {
        "primary_calls": 3,
        "baseline_cost": 0.12,
        "optimized_cost": 0.04,
        "savings": 0.08,
        "savings_ratio": 0.667,
        "source_tokens": 20_000,
        "retained_tokens": 4_000,
        "weighted_source_tokens": 60_000,
        "weighted_retained_tokens": 12_000,
        "decision_counts": {"keep": 0, "summarize": 1, "drop": 0},
        "distiller_cost": 0.005,
        "distiller_prompt_tokens": 200,
        "distiller_prompt_cost": 0.00004,
    }
)
print(view.text)
