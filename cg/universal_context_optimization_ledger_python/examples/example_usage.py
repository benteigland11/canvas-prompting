from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.context_optimization_ledger import DECISION_SUMMARIZE
from src.context_optimization_ledger import ContextOptimizationObservation
from src.context_optimization_ledger import ContextOptimizationPolicy
from src.context_optimization_ledger import TokenRates
from src.context_optimization_ledger import build_context_optimization_report


report = build_context_optimization_report(
    (
        ContextOptimizationObservation(
            label="large_tool_result",
            turn_index=0,
            source_tokens=30_000,
            retained_ratio=0.10,
            decision=DECISION_SUMMARIZE,
        ),
    ),
    primary_rates=TokenRates(input_tokens=2.00, output_tokens=6.00),
    distiller_rates=TokenRates(input_tokens=0.20, output_tokens=0.50),
    primary_calls=5,
    policy=ContextOptimizationPolicy(default_distiller_prompt_tokens=1_000),
)

print(f"savings=${report.savings:.4f}")
print(f"savings_ratio={report.savings_ratio:.2%}")
