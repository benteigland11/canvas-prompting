from __future__ import annotations

from dataclasses import dataclass

from src.context_optimization_ledger import DECISION_DROP
from src.context_optimization_ledger import DECISION_KEEP
from src.context_optimization_ledger import DECISION_SUMMARIZE
from src.context_optimization_ledger import ContextOptimizationObservation
from src.context_optimization_ledger import ContextOptimizationPolicy
from src.context_optimization_ledger import TokenRates
from src.context_optimization_ledger import build_context_optimization_report
from src.context_optimization_ledger import observation_from_context_result_event
from src.context_optimization_ledger import rates_from_metadata


def test_report_kept_events_have_no_savings() -> None:
    report = build_context_optimization_report(
        (
            ContextOptimizationObservation(
                label="read_file",
                turn_index=0,
                source_tokens=1_000,
                decision=DECISION_KEEP,
            ),
        ),
        primary_rates=TokenRates(input_tokens=2.00, output_tokens=6.00),
        distiller_rates=TokenRates(input_tokens=0.20, output_tokens=0.50),
        primary_calls=3,
    )

    assert report.baseline_cost == 0.006
    assert report.optimized_cost == report.baseline_cost
    assert report.savings == 0
    assert report.selected_event_count == 0
    assert report.decision_counts[DECISION_KEEP] == 1


def test_report_models_summarize_savings_with_prompt_tax() -> None:
    report = build_context_optimization_report(
        (
            ContextOptimizationObservation(
                label="large_result",
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

    assert round(report.baseline_cost, 6) == 0.3
    assert report.retained_tokens == 3_000
    assert report.distiller_prompt_tokens == 1_000
    assert report.distiller_prompt_cost == 0.0002
    assert report.optimized_cost < report.baseline_cost
    assert report.savings_ratio > 0.85
    assert report.selected_event_count == 1


def test_report_models_drop_decision() -> None:
    report = build_context_optimization_report(
        (
            ContextOptimizationObservation(
                label="irrelevant_result",
                turn_index=1,
                source_tokens=10_000,
                decision=DECISION_DROP,
            ),
        ),
        primary_rates=TokenRates(input_tokens=2.00),
        distiller_rates=TokenRates(input_tokens=0.20),
        primary_calls=4,
        policy=ContextOptimizationPolicy(default_distiller_prompt_tokens=100),
    )

    event = report.events[0]
    assert event.selected is True
    assert event.retained_tokens == 0
    assert event.future_primary_calls == 3
    assert report.weighted_retained_tokens == 0
    assert report.savings > 0


def test_policy_skips_small_or_late_events() -> None:
    report = build_context_optimization_report(
        (
            ContextOptimizationObservation("small", turn_index=0, source_tokens=10, decision=DECISION_SUMMARIZE),
            ContextOptimizationObservation("late", turn_index=5, source_tokens=10_000, decision=DECISION_SUMMARIZE),
        ),
        primary_rates=TokenRates(input_tokens=2.00),
        distiller_rates=TokenRates(input_tokens=0.20),
        primary_calls=5,
        policy=ContextOptimizationPolicy(min_source_tokens=100, min_future_primary_calls=1),
    )

    assert [event.reason for event in report.events] == ["below_min_source_tokens", "below_min_future_primary_calls"]
    assert report.selected_event_count == 0
    assert report.skipped_event_count == 2


@dataclass(frozen=True)
class ExampleEvent:
    source_id: str
    result_name: str
    estimated_tokens: int
    exact_tokens: int | None
    turn_index: int
    metadata: dict[str, object]


def test_observation_from_context_result_event_prefers_exact_tokens() -> None:
    observation = observation_from_context_result_event(
        ExampleEvent(
            source_id="tool_runner",
            result_name="read_file",
            estimated_tokens=100,
            exact_tokens=80,
            turn_index=2,
            metadata={"path": "README.md"},
        ),
        decision=DECISION_SUMMARIZE,
        retained_ratio=0.25,
        distiller_prompt_tokens=50,
    )

    assert observation.label == "read_file"
    assert observation.source_tokens == 80
    assert observation.turn_index == 2
    assert observation.retained_ratio == 0.25
    assert observation.distiller_prompt_tokens == 50
    assert observation.metadata == {"path": "README.md"}


def test_rates_from_metadata_reads_pricing_shape() -> None:
    rates = rates_from_metadata(
        {
            "pricing": {
                "scale": 1_000,
                "rates": {"input_tokens": 0.02, "output_tokens": 0.05},
            }
        }
    )

    assert rates.input_cost(500) == 0.01
    assert rates.output_cost(200) == 0.01
