from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DECISION_DROP = "drop"
DECISION_SUMMARIZE = "summarize"
DECISION_KEEP = "keep"
DECISIONS = {DECISION_DROP, DECISION_SUMMARIZE, DECISION_KEEP}


@dataclass(frozen=True)
class TokenRates:
    input_tokens: float
    output_tokens: float = 0.0
    scale: float = 1_000_000.0

    def input_cost(self, tokens: int) -> float:
        return _cost(tokens, self.input_tokens, self.scale)

    def output_cost(self, tokens: int) -> float:
        return _cost(tokens, self.output_tokens, self.scale)


@dataclass(frozen=True)
class ContextOptimizationObservation:
    label: str
    turn_index: int
    source_tokens: int
    decision: str = DECISION_KEEP
    retained_tokens: int | None = None
    retained_ratio: float | None = None
    distiller_prompt_tokens: int = 0
    distiller_output_tokens: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ContextOptimizationPolicy:
    default_summary_retained_ratio: float = 0.20
    default_distiller_prompt_tokens: int = 200
    min_source_tokens: int = 1
    min_future_primary_calls: int = 1


@dataclass(frozen=True)
class ContextOptimizationEventReport:
    label: str
    turn_index: int
    decision: str
    source_tokens: int
    retained_tokens: int
    future_primary_calls: int
    baseline_cost: float
    optimized_cost: float
    distiller_cost: float
    retained_context_cost: float
    savings: float
    savings_ratio: float
    profitable: bool
    selected: bool
    reason: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ContextOptimizationReport:
    events: tuple[ContextOptimizationEventReport, ...]
    primary_calls: int
    baseline_cost: float
    optimized_cost: float
    distiller_cost: float
    retained_context_cost: float
    unchanged_context_cost: float
    savings: float
    savings_ratio: float
    profitable: bool
    source_tokens: int
    retained_tokens: int
    weighted_source_tokens: int
    weighted_retained_tokens: int
    selected_event_count: int
    skipped_event_count: int
    decision_counts: dict[str, int]
    distiller_prompt_tokens: int
    distiller_prompt_cost: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_calls": self.primary_calls,
            "baseline_cost": self.baseline_cost,
            "optimized_cost": self.optimized_cost,
            "distiller_cost": self.distiller_cost,
            "retained_context_cost": self.retained_context_cost,
            "unchanged_context_cost": self.unchanged_context_cost,
            "savings": self.savings,
            "savings_ratio": self.savings_ratio,
            "profitable": self.profitable,
            "source_tokens": self.source_tokens,
            "retained_tokens": self.retained_tokens,
            "weighted_source_tokens": self.weighted_source_tokens,
            "weighted_retained_tokens": self.weighted_retained_tokens,
            "selected_event_count": self.selected_event_count,
            "skipped_event_count": self.skipped_event_count,
            "decision_counts": dict(self.decision_counts),
            "distiller_prompt_tokens": self.distiller_prompt_tokens,
            "distiller_prompt_cost": self.distiller_prompt_cost,
            "events": [event_report_to_dict(event) for event in self.events],
        }


def build_context_optimization_report(
    observations: tuple[ContextOptimizationObservation, ...] | list[ContextOptimizationObservation],
    *,
    primary_rates: TokenRates,
    distiller_rates: TokenRates,
    primary_calls: int,
    policy: ContextOptimizationPolicy | None = None,
) -> ContextOptimizationReport:
    resolved_policy = policy or ContextOptimizationPolicy()
    total_primary_calls = max(0, int(primary_calls))
    event_reports: list[ContextOptimizationEventReport] = []
    baseline_cost = 0.0
    optimized_cost = 0.0
    distiller_cost = 0.0
    retained_context_cost = 0.0
    unchanged_context_cost = 0.0
    source_tokens_total = 0
    retained_tokens_total = 0
    weighted_source_tokens = 0
    weighted_retained_tokens = 0
    distiller_prompt_tokens_total = 0
    distiller_prompt_cost_total = 0.0
    decision_counts = {DECISION_DROP: 0, DECISION_SUMMARIZE: 0, DECISION_KEEP: 0}

    for index, observation in enumerate(observations, start=1):
        event = _event_report(
            observation,
            primary_rates=primary_rates,
            distiller_rates=distiller_rates,
            primary_calls=total_primary_calls,
            policy=resolved_policy,
            fallback_label=f"event-{index}",
        )
        event_reports.append(event)
        baseline_cost += event.baseline_cost
        optimized_cost += event.optimized_cost
        source_tokens_total += event.source_tokens
        retained_tokens_total += event.retained_tokens
        weighted_source_tokens += event.source_tokens * event.future_primary_calls
        weighted_retained_tokens += event.retained_tokens * event.future_primary_calls
        decision_counts[event.decision] = decision_counts.get(event.decision, 0) + 1
        if event.selected:
            distiller_cost += event.distiller_cost
            retained_context_cost += event.retained_context_cost
            prompt_tokens = _distiller_prompt_tokens(observation, resolved_policy)
            distiller_prompt_tokens_total += prompt_tokens
            distiller_prompt_cost_total += distiller_rates.input_cost(prompt_tokens)
        else:
            unchanged_context_cost += event.baseline_cost

    savings = baseline_cost - optimized_cost
    selected_count = sum(1 for event in event_reports if event.selected)
    return ContextOptimizationReport(
        events=tuple(event_reports),
        primary_calls=total_primary_calls,
        baseline_cost=baseline_cost,
        optimized_cost=optimized_cost,
        distiller_cost=distiller_cost,
        retained_context_cost=retained_context_cost,
        unchanged_context_cost=unchanged_context_cost,
        savings=savings,
        savings_ratio=savings / baseline_cost if baseline_cost > 0 else 0.0,
        profitable=savings > 0,
        source_tokens=source_tokens_total,
        retained_tokens=retained_tokens_total,
        weighted_source_tokens=weighted_source_tokens,
        weighted_retained_tokens=weighted_retained_tokens,
        selected_event_count=selected_count,
        skipped_event_count=len(event_reports) - selected_count,
        decision_counts=decision_counts,
        distiller_prompt_tokens=distiller_prompt_tokens_total,
        distiller_prompt_cost=distiller_prompt_cost_total,
    )


def observation_from_context_result_event(
    event: Any,
    *,
    decision: str = DECISION_KEEP,
    retained_ratio: float | None = None,
    distiller_prompt_tokens: int = 0,
) -> ContextOptimizationObservation:
    metadata = dict(getattr(event, "metadata", {}) or {})
    label = str(getattr(event, "result_name", "") or getattr(event, "source_id", "") or "")
    return ContextOptimizationObservation(
        label=label,
        turn_index=_non_negative_int(getattr(event, "turn_index", 0)),
        source_tokens=_event_token_count(event),
        decision=_normalize_decision(decision),
        retained_ratio=retained_ratio,
        distiller_prompt_tokens=distiller_prompt_tokens,
        metadata=metadata,
    )


def rates_from_metadata(metadata: dict[str, Any] | None) -> TokenRates:
    pricing = dict((metadata or {}).get("pricing", {}) or {})
    rates = dict(pricing.get("rates", {}) or {})
    return TokenRates(
        input_tokens=float(rates.get("input_tokens", 0.0) or 0.0),
        output_tokens=float(rates.get("output_tokens", 0.0) or 0.0),
        scale=float(pricing.get("scale", 1_000_000.0) or 1_000_000.0),
    )


def event_report_to_dict(event: ContextOptimizationEventReport) -> dict[str, Any]:
    return {
        "label": event.label,
        "turn_index": event.turn_index,
        "decision": event.decision,
        "source_tokens": event.source_tokens,
        "retained_tokens": event.retained_tokens,
        "future_primary_calls": event.future_primary_calls,
        "baseline_cost": event.baseline_cost,
        "optimized_cost": event.optimized_cost,
        "distiller_cost": event.distiller_cost,
        "retained_context_cost": event.retained_context_cost,
        "savings": event.savings,
        "savings_ratio": event.savings_ratio,
        "profitable": event.profitable,
        "selected": event.selected,
        "reason": event.reason,
        "metadata": dict(event.metadata or {}),
    }


def _event_report(
    observation: ContextOptimizationObservation,
    *,
    primary_rates: TokenRates,
    distiller_rates: TokenRates,
    primary_calls: int,
    policy: ContextOptimizationPolicy,
    fallback_label: str,
) -> ContextOptimizationEventReport:
    decision = _normalize_decision(observation.decision)
    source_tokens = max(0, int(observation.source_tokens))
    retained_tokens = _retained_tokens(observation, policy, decision)
    future_primary_calls = max(0, primary_calls - max(0, int(observation.turn_index)))
    baseline_cost = primary_rates.input_cost(source_tokens * future_primary_calls)
    retained_context_cost = primary_rates.input_cost(retained_tokens * future_primary_calls)
    prompt_tokens = _distiller_prompt_tokens(observation, policy)
    distiller_output_tokens = (
        max(0, int(observation.distiller_output_tokens))
        if observation.distiller_output_tokens is not None
        else retained_tokens
    )
    distiller_cost = (
        distiller_rates.input_cost(source_tokens + prompt_tokens)
        + distiller_rates.output_cost(distiller_output_tokens)
    )
    selected, reason = _selection_reason(
        decision=decision,
        source_tokens=source_tokens,
        future_primary_calls=future_primary_calls,
        policy=policy,
    )
    optimized_cost = (
        distiller_cost + retained_context_cost
        if selected
        else baseline_cost
    )
    savings = baseline_cost - optimized_cost
    return ContextOptimizationEventReport(
        label=observation.label or fallback_label,
        turn_index=max(0, int(observation.turn_index)),
        decision=decision,
        source_tokens=source_tokens,
        retained_tokens=retained_tokens if selected else source_tokens,
        future_primary_calls=future_primary_calls,
        baseline_cost=baseline_cost,
        optimized_cost=optimized_cost,
        distiller_cost=distiller_cost if selected else 0.0,
        retained_context_cost=retained_context_cost if selected else baseline_cost,
        savings=savings,
        savings_ratio=savings / baseline_cost if baseline_cost > 0 else 0.0,
        profitable=savings > 0,
        selected=selected,
        reason=reason,
        metadata=dict(observation.metadata or {}),
    )


def _selection_reason(
    *,
    decision: str,
    source_tokens: int,
    future_primary_calls: int,
    policy: ContextOptimizationPolicy,
) -> tuple[bool, str]:
    if decision == DECISION_KEEP:
        return False, "kept"
    if source_tokens < max(0, int(policy.min_source_tokens)):
        return False, "below_min_source_tokens"
    if future_primary_calls < max(0, int(policy.min_future_primary_calls)):
        return False, "below_min_future_primary_calls"
    return True, decision


def _retained_tokens(
    observation: ContextOptimizationObservation,
    policy: ContextOptimizationPolicy,
    decision: str,
) -> int:
    source_tokens = max(0, int(observation.source_tokens))
    if decision == DECISION_DROP:
        return 0
    if decision == DECISION_KEEP:
        return source_tokens
    if observation.retained_tokens is not None:
        return max(0, int(observation.retained_tokens))
    ratio = observation.retained_ratio
    if ratio is None:
        ratio = policy.default_summary_retained_ratio
    return max(0, int(round(source_tokens * max(0.0, min(1.0, float(ratio))))))


def _distiller_prompt_tokens(
    observation: ContextOptimizationObservation,
    policy: ContextOptimizationPolicy,
) -> int:
    if observation.distiller_prompt_tokens:
        return max(0, int(observation.distiller_prompt_tokens))
    return max(0, int(policy.default_distiller_prompt_tokens))


def _normalize_decision(decision: str) -> str:
    normalized = str(decision or "").strip().lower()
    return normalized if normalized in DECISIONS else DECISION_KEEP


def _event_token_count(event: Any) -> int:
    value = getattr(event, "exact_tokens", None)
    if value is None:
        value = getattr(event, "estimated_tokens", 0)
    return _non_negative_int(value)


def _non_negative_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, resolved)


def _cost(tokens: int, rate: float, scale: float) -> float:
    resolved_scale = float(scale or 1.0)
    if resolved_scale <= 0:
        resolved_scale = 1.0
    return max(0, int(tokens)) * float(rate) / resolved_scale
