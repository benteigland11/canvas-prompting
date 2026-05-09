from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DECISION_KEEP = "keep"
DECISION_SUMMARIZE = "summarize"
DECISION_DROP = "drop"


@dataclass(frozen=True)
class PayloadProjection:
    content: str
    decision: str
    replaced: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "decision": self.decision,
            "replaced": self.replaced,
            "reason": self.reason,
        }


def project_payload_content(
    content: Any,
    *,
    projection: dict[str, Any] | object | None = None,
    metadata: dict[str, Any] | object | None = None,
    fallback_name: str = "item",
    fallback_status: str = "complete",
    max_summary_chars: int = 900,
) -> PayloadProjection:
    """Project retained content into a payload-safe representation."""

    original = str(content or "")
    projection_data = _mapping(projection)
    metadata_data = _mapping(metadata)
    decision = str(projection_data.get("decision", "") or DECISION_KEEP)
    reason = str(projection_data.get("reason", "") or "context_management")
    if decision == DECISION_DROP:
        return PayloadProjection(
            content=format_omitted_content(
                projection=projection_data,
                metadata=metadata_data,
                fallback_name=fallback_name,
                fallback_status=fallback_status,
            ),
            decision=decision,
            replaced=True,
            reason=reason,
        )
    if decision == DECISION_SUMMARIZE:
        return PayloadProjection(
            content=format_summarized_content(
                original,
                projection=projection_data,
                metadata=metadata_data,
                fallback_name=fallback_name,
                fallback_status=fallback_status,
                max_summary_chars=max_summary_chars,
            ),
            decision=decision,
            replaced=True,
            reason=reason,
        )
    return PayloadProjection(content=original, decision=decision or DECISION_KEEP, replaced=False, reason=reason)


def format_omitted_content(
    *,
    projection: dict[str, Any] | object | None = None,
    metadata: dict[str, Any] | object | None = None,
    fallback_name: str = "item",
    fallback_status: str = "complete",
) -> str:
    projection_data = _mapping(projection)
    metadata_data = _mapping(metadata)
    name = _projection_name(projection_data, metadata_data, fallback_name)
    status = _projection_status(projection_data, metadata_data, fallback_status)
    token_count = _projection_token_count(projection_data)
    reason = str(projection_data.get("reason", "") or "context_management")
    token_text = f", {token_count} tokens" if token_count else ""
    return f"[content omitted: {name}, {status}{token_text}, reason: {reason}, available in session log]"


def format_summarized_content(
    content: Any,
    *,
    projection: dict[str, Any] | object | None = None,
    metadata: dict[str, Any] | object | None = None,
    fallback_name: str = "item",
    fallback_status: str = "complete",
    max_summary_chars: int = 900,
) -> str:
    projection_data = _mapping(projection)
    metadata_data = _mapping(metadata)
    name = _projection_name(projection_data, metadata_data, fallback_name)
    status = _projection_status(projection_data, metadata_data, fallback_status)
    token_count = _projection_token_count(projection_data)
    reason = str(projection_data.get("reason", "") or "context_management")
    token_text = f", {token_count} tokens" if token_count else ""
    summary_text = _projection_summary_text(projection_data, metadata_data)
    excerpt = compact_text_excerpt(summary_text or str(content or ""), max_chars=max_summary_chars)
    if not excerpt:
        excerpt = "(empty content)"
    return (
        f"[content summarized: {name}, {status}{token_text}, reason: {reason}, "
        "available in session log]\n"
        f"{excerpt}"
    )


def compact_text_excerpt(content: Any, *, max_chars: int = 900) -> str:
    text = _normalize_text(str(content or ""))
    limit = max(80, int(max_chars))
    if len(text) <= limit:
        return text

    marker = "\n... middle omitted ...\n"
    if limit <= len(marker) + 40:
        return text[:limit].rstrip()

    head_len = max(20, (limit - len(marker)) // 2)
    tail_len = max(20, limit - len(marker) - head_len)
    head = text[:head_len].rstrip()
    tail = text[-tail_len:].lstrip()
    return f"{head}{marker}{tail}"


def _projection_name(projection: dict[str, Any], metadata: dict[str, Any], fallback: str) -> str:
    projection_metadata = _mapping(projection.get("metadata"))
    return str(
        projection.get("name", "")
        or projection_metadata.get("name", "")
        or metadata.get("tool_name", "")
        or metadata.get("name", "")
        or fallback
    )


def _projection_status(projection: dict[str, Any], metadata: dict[str, Any], fallback: str) -> str:
    projection_metadata = _mapping(projection.get("metadata"))
    return str(projection.get("status", "") or projection_metadata.get("status", "") or metadata.get("status", "") or fallback)


def _projection_token_count(projection: dict[str, Any]) -> int:
    projection_metadata = _mapping(projection.get("metadata"))
    return _non_negative_int(projection_metadata.get("linked_token_count") or projection.get("token_count"))


def _projection_summary_text(projection: dict[str, Any], metadata: dict[str, Any]) -> str:
    projection_metadata = _mapping(projection.get("metadata"))
    return str(
        projection.get("summary_text", "")
        or projection_metadata.get("summary_text", "")
        or metadata.get("context_summary_text", "")
        or metadata.get("summary_text", "")
        or ""
    ).strip()


def _normalize_text(content: str) -> str:
    lines = [line.rstrip() for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _non_negative_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, resolved)
