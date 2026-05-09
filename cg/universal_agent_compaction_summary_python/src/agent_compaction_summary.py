from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import uuid4


DEFAULT_SUMMARY_SECTIONS = (
    "User goal and standing preferences",
    "Decisions made",
    "Files, commands, and external systems touched",
    "Current state and unresolved risks",
    "Next smallest useful steps",
)


@dataclass(frozen=True)
class CompactionSummarySource:
    """A source item that should be considered by a compaction summarizer."""

    source_id: str
    source_type: str
    text: str
    token_count: int = 0
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "text": self.text,
            "token_count": self.token_count,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class CompactionSummaryRecord:
    """Durable metadata for a completed context-window summary."""

    compaction_id: str
    summary_message_id: str
    strategy: str
    model: str
    input_tokens_before: int
    output_tokens_after: int
    source_event_ids: tuple[str, ...]
    source_message_ids: tuple[str, ...]
    summary_text: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "compaction_id": self.compaction_id,
            "summary_message_id": self.summary_message_id,
            "strategy": self.strategy,
            "model": self.model,
            "input_tokens_before": self.input_tokens_before,
            "output_tokens_after": self.output_tokens_after,
            "source_event_ids": list(self.source_event_ids),
            "source_message_ids": list(self.source_message_ids),
            "summary_text": self.summary_text,
            "metadata": dict(self.metadata),
        }


def build_compaction_summary_prompt(
    sources: Sequence[Mapping[str, Any] | CompactionSummarySource],
    *,
    window_state: Mapping[str, Any] | None = None,
    day_phase: Mapping[str, Any] | None = None,
    sections: Sequence[str] = DEFAULT_SUMMARY_SECTIONS,
    max_source_chars: int = 24000,
) -> str:
    """Build a compact, model-ready prompt for an end-of-window summary."""

    normalized_sources = tuple(_source_to_dict(source) for source in sources)
    budget = max(1000, int(max_source_chars or 0))
    lines = [
        "Create a durable context-window handoff summary.",
        "Preserve facts needed for future turns and omit transient chatter.",
        "",
        "Required sections:",
    ]
    for section in sections:
        label = str(section or "").strip()
        if label:
            lines.append(f"- {label}")
    if window_state:
        lines.extend(("", "Context window:", _compact_mapping(window_state)))
    if day_phase:
        lines.extend(("", "Day phase:", _compact_mapping(day_phase)))
    lines.extend(("", "Sources:"))
    remaining = budget
    for source in normalized_sources:
        header = f"[{source['source_type']}:{source['source_id']}]"
        text = str(source.get("text", "") or "").strip()
        if not text:
            continue
        if remaining <= 0:
            lines.append("[additional sources omitted: source budget exhausted]")
            break
        clipped = text[:remaining]
        if len(text) > len(clipped):
            clipped = clipped.rstrip() + "\n[truncated]"
        lines.extend((header, clipped, ""))
        remaining -= len(clipped)
    return "\n".join(lines).strip()


def build_compaction_summary_record(
    *,
    summary_text: str,
    model: str,
    input_tokens_before: int,
    output_tokens_after: int,
    source_event_ids: Sequence[str] = (),
    source_message_ids: Sequence[str] = (),
    strategy: str = "end_of_window",
    summary_message_id: str = "",
    compaction_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> CompactionSummaryRecord:
    """Build a validated compaction summary record from model output and usage."""

    return CompactionSummaryRecord(
        compaction_id=str(compaction_id or f"compact_{uuid4().hex[:16]}"),
        summary_message_id=str(summary_message_id or f"msg_summary_{uuid4().hex[:16]}"),
        strategy=str(strategy or "end_of_window"),
        model=str(model or ""),
        input_tokens_before=max(0, int(input_tokens_before or 0)),
        output_tokens_after=max(0, int(output_tokens_after or 0)),
        source_event_ids=tuple(str(value) for value in source_event_ids if str(value).strip()),
        source_message_ids=tuple(str(value) for value in source_message_ids if str(value).strip()),
        summary_text=str(summary_text or "").strip(),
        metadata=dict(metadata or {}),
    )


def _source_to_dict(source: Mapping[str, Any] | CompactionSummarySource) -> dict[str, Any]:
    payload = source.to_dict() if isinstance(source, CompactionSummarySource) else dict(source)
    return {
        "source_id": str(payload.get("source_id", "") or payload.get("id", "") or "source"),
        "source_type": str(payload.get("source_type", "") or payload.get("type", "") or "text"),
        "text": str(payload.get("text", "") or payload.get("content", "") or ""),
        "token_count": max(0, int(payload.get("token_count", 0) or 0)),
        "metadata": dict(payload.get("metadata", {}) or {}),
    }


def _compact_mapping(payload: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key, value in sorted(dict(payload).items()):
        if value in ("", None, (), [], {}):
            continue
        parts.append(f"- {key}: {value}")
    return "\n".join(parts) if parts else "- none"
