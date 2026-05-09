from __future__ import annotations

from src.context_optimization_report import format_context_optimization_report
from src.context_optimization_report import format_context_usage_report


def test_format_context_optimization_report_includes_observed_and_potential_savings() -> None:
    view = format_context_optimization_report(
        {
            "primary_calls": 4,
            "baseline_cost": 0.24,
            "optimized_cost": 0.08,
            "savings": 0.16,
            "savings_ratio": 0.666,
            "source_tokens": 30_000,
            "retained_tokens": 3_000,
            "weighted_source_tokens": 120_000,
            "weighted_retained_tokens": 12_000,
            "decision_counts": {"keep": 0, "summarize": 1, "drop": 0},
            "distiller_cost": 0.01,
            "distiller_prompt_tokens": 1_000,
            "distiller_prompt_cost": 0.0002,
            "primary_target_id": "primary",
            "distiller_target_id": "small",
            "potential_summarize": {"savings": 0.18, "savings_ratio": 0.75, "retained_tokens": 3_000},
            "potential_drop": {"savings": 0.20, "savings_ratio": 0.833, "retained_tokens": 0},
            "events": (
                {
                    "label": "read_file",
                    "decision": "summarize",
                    "source_tokens": 30_000,
                    "retained_tokens": 3_000,
                    "future_primary_calls": 4,
                    "savings": 0.16,
                },
            ),
        },
        title="Cost",
    )

    assert view.title == "Cost"
    assert "observed: baseline $0.24 | optimized $0.08 | savings $0.16 (66.6%)" in view.text
    assert "if summarized: savings $0.18 (75.0%) | retained 3K" in view.text
    assert "if dropped: savings $0.20 (83.3%) | retained 0" in view.text
    assert "- read_file: summarize | source 30K | retained 3K | future calls 4 | savings $0.16" in view.text


def test_format_context_optimization_report_handles_empty_report() -> None:
    view = format_context_optimization_report(None)

    assert view.text == "Context Optimization\nNo context optimization data recorded."


def test_format_context_usage_report_includes_state_and_ledger() -> None:
    view = format_context_usage_report(
        {
            "state": {
                "used_tokens": 123_000,
                "max_tokens": 500_000,
                "reserve_tokens": 50_000,
                "source": "actual",
                "level": "normal",
            },
            "result_events": (
                {"estimated_tokens": 100, "exact_tokens": 80},
                {"estimated_tokens": 200, "exact_tokens": None},
            ),
        }
    )

    assert "current: 123K/500K | reserve 50K | source actual | level normal" in view.text
    assert "tool result ledger: 2 events | estimated 300 | exact 80 | pending tokenization 1" in view.text


def test_format_context_usage_report_includes_management_decisions() -> None:
    view = format_context_usage_report(
        {
            "state": {
                "used_tokens": 20_000,
                "max_tokens": 500_000,
                "reserve_tokens": 50_000,
                "source": "estimated",
                "level": "normal",
            },
            "result_events": (),
        },
        context_management={
            "input_tokens": 30_000,
            "keep_tokens": 18_000,
            "summarize_tokens": 6_000,
            "drop_tokens": 6_000,
            "decision_counts": {"keep": 8, "summarize": 2, "drop": 3},
            "distiller": {"generated": 1, "cached": 2, "failed": 0, "model": "small-model"},
        },
    )

    assert "context management: keep 8 | summarize 2 | drop 3" in view.text
    assert "managed tokens: input 30K | retained 24K | keep 18K | summarize 6K | drop 6K" in view.text
    assert "drop ratio: 20.0%" in view.text
    assert "distiller: generated 1 | cached 2 | failed 0 | model small-model" in view.text
