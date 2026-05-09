from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextOptimizationReportView:
    title: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join((self.title, *self.lines))


def format_context_optimization_report(
    report: dict[str, Any] | object | None,
    *,
    title: str = "Context Optimization",
    include_events: bool = True,
    max_events: int = 8,
) -> ContextOptimizationReportView:
    data = _mapping(report)
    if not data:
        return ContextOptimizationReportView(title=title, lines=("No context optimization data recorded.",))

    lines = [
        f"primary calls: {_int(data.get('primary_calls'))}",
        (
            "observed: "
            f"baseline {_money(data.get('baseline_cost'))} | "
            f"optimized {_money(data.get('optimized_cost'))} | "
            f"savings {_money(data.get('savings'))} ({_percent(data.get('savings_ratio'))})"
        ),
        (
            "tokens: "
            f"source {_count(data.get('source_tokens'))} | "
            f"retained {_count(data.get('retained_tokens'))} | "
            f"weighted saved {_count(_int(data.get('weighted_source_tokens')) - _int(data.get('weighted_retained_tokens')))}"
        ),
        (
            "decisions: "
            f"keep {_decision_count(data, 'keep')} | "
            f"summarize {_decision_count(data, 'summarize')} | "
            f"drop {_decision_count(data, 'drop')}"
        ),
        (
            "distiller: "
            f"cost {_money(data.get('distiller_cost'))} | "
            f"prompt tax {_count(data.get('distiller_prompt_tokens'))} tokens / {_money(data.get('distiller_prompt_cost'))}"
        ),
    ]

    summarize = _mapping(data.get("potential_summarize"))
    if summarize:
        lines.append(
            "if summarized: "
            f"savings {_money(summarize.get('savings'))} ({_percent(summarize.get('savings_ratio'))}) | "
            f"retained {_count(summarize.get('retained_tokens'))}"
        )
    drop = _mapping(data.get("potential_drop"))
    if drop:
        lines.append(
            "if dropped: "
            f"savings {_money(drop.get('savings'))} ({_percent(drop.get('savings_ratio'))}) | "
            f"retained {_count(drop.get('retained_tokens'))}"
        )

    primary_target = str(data.get("primary_target_id", "") or "")
    distiller_target = str(data.get("distiller_target_id", "") or "")
    if primary_target or distiller_target:
        lines.append(f"targets: primary {primary_target or 'unknown'} | distiller {distiller_target or 'unknown'}")

    if include_events:
        event_lines = _format_events(data.get("events"), max_events=max_events)
        if event_lines:
            lines.append("")
            lines.extend(event_lines)

    return ContextOptimizationReportView(title=title, lines=tuple(lines))


def format_context_usage_report(
    snapshot: dict[str, Any] | object | None,
    *,
    title: str = "Context Usage",
    context_management: dict[str, Any] | object | None = None,
) -> ContextOptimizationReportView:
    data = _mapping(snapshot)
    state = _mapping(data.get("state"))
    events = tuple(item for item in data.get("result_events", ()) or () if isinstance(item, dict))
    estimated = sum(_int(event.get("estimated_tokens")) for event in events)
    exact = sum(_int(event.get("exact_tokens")) for event in events)
    pending = sum(1 for event in events if event.get("exact_tokens") in (None, ""))
    lines = [
        (
            "current: "
            f"{_count(state.get('used_tokens'))}/{_count(state.get('max_tokens'))} | "
            f"reserve {_count(state.get('reserve_tokens'))} | "
            f"source {state.get('source', 'unknown') or 'unknown'} | "
            f"level {state.get('level', 'unknown') or 'unknown'}"
        ),
        (
            "tool result ledger: "
            f"{len(events)} events | estimated {_count(estimated)} | "
            f"exact {_count(exact)} | pending tokenization {pending}"
        ),
    ]
    management_lines = _format_context_management(context_management)
    if management_lines:
        lines.append("")
        lines.extend(management_lines)
    return ContextOptimizationReportView(title=title, lines=tuple(lines))


def _format_context_management(plan: dict[str, Any] | object | None) -> tuple[str, ...]:
    data = _mapping(plan)
    if not data or data.get("error"):
        return ()

    counts = _mapping(data.get("decision_counts"))
    keep_count = _int(counts.get("keep"))
    summarize_count = _int(counts.get("summarize"))
    drop_count = _int(counts.get("drop"))
    input_tokens = _int(data.get("input_tokens"))
    keep_tokens = _int(data.get("keep_tokens"))
    summarize_tokens = _int(data.get("summarize_tokens"))
    drop_tokens = _int(data.get("drop_tokens"))
    managed_count = keep_count + summarize_count + drop_count
    if managed_count == 0 and input_tokens == 0:
        return ()

    retained_tokens = keep_tokens + summarize_tokens
    lines = [
        (
            "context management: "
            f"keep {keep_count} | summarize {summarize_count} | drop {drop_count}"
        ),
        (
            "managed tokens: "
            f"input {_count(input_tokens)} | retained {_count(retained_tokens)} | "
            f"keep {_count(keep_tokens)} | summarize {_count(summarize_tokens)} | drop {_count(drop_tokens)}"
        ),
    ]
    if input_tokens > 0 and drop_tokens > 0:
        lines.append(f"drop ratio: {_percent(drop_tokens / input_tokens)}")
    distiller = _mapping(data.get("distiller"))
    if distiller:
        lines.append(
            "distiller: "
            f"generated {_int(distiller.get('generated'))} | "
            f"cached {_int(distiller.get('cached'))} | "
            f"failed {_int(distiller.get('failed'))} | "
            f"model {distiller.get('model', 'unknown') or 'unknown'}"
        )
    return tuple(lines)


def _format_events(events: Any, *, max_events: int) -> tuple[str, ...]:
    items = tuple(item for item in events or () if isinstance(item, dict))
    if not items:
        return ()
    limit = max(0, int(max_events))
    lines = ["events:"]
    for item in items[:limit]:
        lines.append(
            "- "
            f"{item.get('label', 'event')}: "
            f"{item.get('decision', 'unknown')} | "
            f"source {_count(item.get('source_tokens'))} | "
            f"retained {_count(item.get('retained_tokens'))} | "
            f"future calls {_int(item.get('future_primary_calls'))} | "
            f"savings {_money(item.get('savings'))}"
        )
    if len(items) > limit:
        lines.append(f"- ... {len(items) - limit} more")
    return tuple(lines)


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return _mapping(value.to_dict())
    return {}


def _decision_count(data: dict[str, Any], decision: str) -> int:
    return _int(_mapping(data.get("decision_counts")).get(decision))


def _int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _money(value: Any) -> str:
    amount = _float(value)
    if abs(amount) < 0.0001:
        return "$0"
    if abs(amount) < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def _percent(value: Any) -> str:
    return f"{_float(value) * 100:.1f}%"


def _count(value: Any) -> str:
    count = _int(value)
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(count)
