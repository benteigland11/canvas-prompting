from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DECISION_KEEP = "keep"
DECISION_SUMMARIZE = "summarize"
DECISION_DROP = "drop"


@dataclass(frozen=True)
class RetentionPolicyConfig:
    keep_recent_count: int = 8
    summarize_after_count: int = 8
    drop_after_count: int = 40
    summarize_min_tokens: int = 500
    drop_successful_tool_results_after_count: int = 24
    always_keep_statuses: tuple[str, ...] = ("streaming",)
    always_keep_roles: tuple[str, ...] = ("system",)


@dataclass(frozen=True)
class RetentionItem:
    item_id: str
    item_type: str
    role: str = ""
    status: str = ""
    name: str = ""
    token_count: int = 0
    age_index: int = 0
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RetentionDecision:
    item_id: str
    decision: str
    reason: str
    token_count: int = 0
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "decision": self.decision,
            "reason": self.reason,
            "token_count": self.token_count,
            "metadata": dict(self.metadata or {}),
        }


def decide_retention(
    item: RetentionItem | dict[str, Any],
    *,
    config: RetentionPolicyConfig | None = None,
) -> RetentionDecision:
    resolved = retention_item_from_any(item)
    policy = config or RetentionPolicyConfig()
    role = resolved.role.strip().lower()
    status = resolved.status.strip().lower()
    item_type = resolved.item_type.strip().lower()

    if role in {value.lower() for value in policy.always_keep_roles}:
        return _decision(resolved, DECISION_KEEP, "always_keep_role")
    if status in {value.lower() for value in policy.always_keep_statuses}:
        return _decision(resolved, DECISION_KEEP, "always_keep_status")
    if resolved.age_index < max(0, policy.keep_recent_count):
        return _decision(resolved, DECISION_KEEP, "recent")
    if (
        item_type == "tool_result"
        and status == "success"
        and resolved.age_index >= max(0, policy.drop_successful_tool_results_after_count)
    ):
        return _decision(resolved, DECISION_DROP, "old_successful_tool_result")
    if resolved.age_index >= max(0, policy.drop_after_count):
        return _decision(resolved, DECISION_DROP, "old")
    if resolved.age_index >= max(0, policy.summarize_after_count) and resolved.token_count >= max(
        0,
        policy.summarize_min_tokens,
    ):
        return _decision(resolved, DECISION_SUMMARIZE, "old_large")
    return _decision(resolved, DECISION_KEEP, "small_or_recent")


def decide_retention_many(
    items: tuple[RetentionItem | dict[str, Any], ...] | list[RetentionItem | dict[str, Any]],
    *,
    config: RetentionPolicyConfig | None = None,
) -> tuple[RetentionDecision, ...]:
    return tuple(decide_retention(item, config=config) for item in tuple(items))


def retention_item_from_any(value: RetentionItem | dict[str, Any] | Any) -> RetentionItem:
    if isinstance(value, RetentionItem):
        return value
    payload = dict(value) if isinstance(value, dict) else {
        "item_id": getattr(value, "item_id", ""),
        "item_type": getattr(value, "item_type", ""),
        "role": getattr(value, "role", ""),
        "status": getattr(value, "status", ""),
        "name": getattr(value, "name", ""),
        "token_count": getattr(value, "token_count", 0),
        "age_index": getattr(value, "age_index", 0),
        "metadata": getattr(value, "metadata", {}),
    }
    return RetentionItem(
        item_id=str(payload.get("item_id", "") or ""),
        item_type=str(payload.get("item_type", "") or ""),
        role=str(payload.get("role", "") or ""),
        status=str(payload.get("status", "") or ""),
        name=str(payload.get("name", "") or ""),
        token_count=_non_negative_int(payload.get("token_count")),
        age_index=_non_negative_int(payload.get("age_index")),
        metadata=dict(payload.get("metadata", {}) or {}),
    )


def decision_counts(decisions: tuple[RetentionDecision, ...] | list[RetentionDecision]) -> dict[str, int]:
    counts = {DECISION_KEEP: 0, DECISION_SUMMARIZE: 0, DECISION_DROP: 0}
    for decision in tuple(decisions):
        counts[decision.decision] = counts.get(decision.decision, 0) + 1
    return counts


def _decision(item: RetentionItem, decision: str, reason: str) -> RetentionDecision:
    return RetentionDecision(
        item_id=item.item_id,
        decision=decision,
        reason=reason,
        token_count=item.token_count,
        metadata={
            "item_type": item.item_type,
            "role": item.role,
            "status": item.status,
            "name": item.name,
            **dict(item.metadata or {}),
        },
    )


def _non_negative_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, resolved)
