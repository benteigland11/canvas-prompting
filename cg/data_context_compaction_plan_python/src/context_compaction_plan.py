from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import Any
import json


DECISION_KEEP = "keep"
DECISION_SUMMARIZE = "summarize"
DECISION_DROP = "drop"


@dataclass(frozen=True)
class ContextPlanItem:
    item_id: str
    item_type: str
    content: str
    role: str = ""
    status: str = ""
    name: str = ""
    token_count: int = 0
    age_index: int = 0
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "role": self.role,
            "status": self.status,
            "name": self.name,
            "content": self.content,
            "token_count": self.token_count,
            "age_index": self.age_index,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class ContextPlanDecision:
    item: ContextPlanItem
    decision: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = self.item.to_dict()
        payload.update({"decision": self.decision, "reason": self.reason})
        return payload


@dataclass(frozen=True)
class ContextCompactionPlan:
    decisions: tuple[ContextPlanDecision, ...]
    input_tokens: int
    keep_tokens: int
    summarize_tokens: int
    drop_tokens: int
    decision_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "keep_tokens": self.keep_tokens,
            "summarize_tokens": self.summarize_tokens,
            "drop_tokens": self.drop_tokens,
            "decision_counts": dict(self.decision_counts),
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


def build_context_items(
    *,
    messages: tuple[Any, ...] | list[Any] = (),
    result_events: tuple[Any, ...] | list[Any] = (),
    chars_per_token: float = 4.0,
) -> tuple[ContextPlanItem, ...]:
    items: list[ContextPlanItem] = []
    message_list = tuple(messages)
    result_list = tuple(result_events)
    total = len(message_list) + len(result_list)
    index = 0
    for message in message_list:
        content = str(_get_value(message, "content") or "")
        item_id = str(_get_value(message, "message_id") or f"message_{index}")
        items.append(
            ContextPlanItem(
                item_id=item_id,
                item_type="message",
                role=str(_get_value(message, "role") or ""),
                status=str(_get_value(message, "status") or ""),
                name=str(_get_value(message, "name") or ""),
                content=content,
                token_count=_estimate_tokens(content, chars_per_token),
                age_index=max(0, total - index - 1),
                metadata=_mapping(_get_value(message, "metadata")),
            )
        )
        index += 1
    for event in result_list:
        content = str(_get_value(event, "source_text") or _get_value(event, "result") or "")
        sequence = _get_value(event, "sequence")
        item_id = f"tool_result_{sequence}" if sequence not in ("", None) else f"tool_result_{index}"
        token_count = _optional_int(_get_value(event, "exact_tokens"))
        if token_count is None:
            token_count = _optional_int(_get_value(event, "estimated_tokens"))
        if token_count is None:
            token_count = _estimate_tokens(content, chars_per_token)
        items.append(
            ContextPlanItem(
                item_id=str(item_id),
                item_type="tool_result",
                role="tool",
                status=str(_get_value(event, "status") or ""),
                name=str(_get_value(event, "result_name") or ""),
                content=content,
                token_count=max(0, token_count),
                age_index=max(0, total - index - 1),
                metadata=_mapping(_get_value(event, "metadata")),
            )
        )
        index += 1
    return tuple(items)


def build_context_compaction_plan(
    items: tuple[ContextPlanItem, ...] | list[ContextPlanItem],
    *,
    decisions: tuple[Any, ...] | list[Any],
) -> ContextCompactionPlan:
    item_by_id = {item.item_id: item for item in tuple(items)}
    plan_decisions: list[ContextPlanDecision] = []
    for decision in tuple(decisions):
        item_id = str(_get_value(decision, "item_id") or "")
        item = item_by_id.get(item_id)
        if item is None:
            continue
        item = _apply_decision_item_overrides(item, decision)
        plan_decisions.append(
            ContextPlanDecision(
                item=item,
                decision=str(_get_value(decision, "decision") or DECISION_KEEP),
                reason=str(_get_value(decision, "reason") or ""),
            )
        )
    counts = {DECISION_KEEP: 0, DECISION_SUMMARIZE: 0, DECISION_DROP: 0}
    keep_tokens = 0
    summarize_tokens = 0
    drop_tokens = 0
    for decision in plan_decisions:
        counts[decision.decision] = counts.get(decision.decision, 0) + 1
        if decision.decision == DECISION_DROP:
            drop_tokens += decision.item.token_count
        elif decision.decision == DECISION_SUMMARIZE:
            summarize_tokens += decision.item.token_count
        else:
            keep_tokens += decision.item.token_count
    return ContextCompactionPlan(
        decisions=tuple(plan_decisions),
        input_tokens=sum(item.token_count for item in item_by_id.values()),
        keep_tokens=keep_tokens,
        summarize_tokens=summarize_tokens,
        drop_tokens=drop_tokens,
        decision_counts=counts,
    )


def _apply_decision_item_overrides(item: ContextPlanItem, decision: Any) -> ContextPlanItem:
    metadata = dict(item.metadata or {})
    metadata.update(_mapping(_get_value(decision, "metadata")))
    summary_text = str(_get_value(decision, "summary_text") or "")
    if summary_text:
        metadata["summary_text"] = summary_text

    updates: dict[str, Any] = {"metadata": metadata}
    for field_name in ("role", "status", "name", "content", "item_type"):
        value = _get_value(decision, field_name)
        if value not in ("", None):
            updates[field_name] = str(value)
    token_count = _optional_int(_get_value(decision, "token_count"))
    if token_count is not None:
        updates["token_count"] = token_count
    return replace(item, **updates)


def plan_summary_text(plan: ContextCompactionPlan) -> str:
    return (
        f"context plan: keep {plan.decision_counts.get(DECISION_KEEP, 0)}, "
        f"summarize {plan.decision_counts.get(DECISION_SUMMARIZE, 0)}, "
        f"drop {plan.decision_counts.get(DECISION_DROP, 0)} "
        f"({plan.input_tokens} input tokens)"
    )


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key, "")
    return getattr(value, key, "")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_int(value: Any) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    return resolved if resolved >= 0 else None


def _estimate_tokens(content: Any, chars_per_token: float) -> int:
    text = serialize_content(content).strip()
    if not text:
        return 0
    divisor = chars_per_token if chars_per_token > 0 else 4.0
    return max(1, int((len(text) + divisor - 1) // divisor))


def serialize_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=repr, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)
