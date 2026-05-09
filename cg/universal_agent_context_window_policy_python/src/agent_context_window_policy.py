from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


WINDOW_OPEN = "open"
WINDOW_CLOSING = "closing"
WINDOW_COMPACTED = "compacted"


@dataclass(frozen=True)
class ContextWindowPolicyConfig:
    """Token thresholds for a bounded agent context window."""

    max_tokens: int = 400000
    closing_ratio: float = 0.9


@dataclass(frozen=True)
class ContextWindowState:
    """Current context-window state plus prompt/UI guidance."""

    phase: str
    used_tokens: int
    max_tokens: int
    closing_tokens: int
    soft_stop_pending: bool
    label: str
    prompt_guidance: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "used_tokens": self.used_tokens,
            "max_tokens": self.max_tokens,
            "closing_tokens": self.closing_tokens,
            "soft_stop_pending": self.soft_stop_pending,
            "label": self.label,
            "prompt_guidance": self.prompt_guidance,
            "reason": self.reason,
        }


def evaluate_context_window(
    *,
    used_tokens: int,
    config: ContextWindowPolicyConfig | None = None,
    current_phase: str = WINDOW_OPEN,
    compacted: bool = False,
) -> ContextWindowState:
    """Evaluate whether a context window is open, closing, or compacted."""

    resolved_config = config or ContextWindowPolicyConfig()
    resolved_used = max(0, int(used_tokens or 0))
    max_tokens = max(1, int(resolved_config.max_tokens or 1))
    ratio = float(resolved_config.closing_ratio or 0.0)
    ratio = min(1.0, max(0.0, ratio))
    closing_tokens = max(1, min(max_tokens, int(max_tokens * ratio)))
    normalized_phase = _normalize_phase(current_phase)

    if compacted or normalized_phase == WINDOW_COMPACTED:
        return _state(
            WINDOW_COMPACTED,
            used_tokens=resolved_used,
            max_tokens=max_tokens,
            closing_tokens=closing_tokens,
            soft_stop_pending=False,
            reason="context window already compacted",
        )

    if resolved_used >= closing_tokens:
        return _state(
            WINDOW_CLOSING,
            used_tokens=resolved_used,
            max_tokens=max_tokens,
            closing_tokens=closing_tokens,
            soft_stop_pending=True,
            reason="closing threshold reached",
        )

    return _state(
        WINDOW_OPEN,
        used_tokens=resolved_used,
        max_tokens=max_tokens,
        closing_tokens=closing_tokens,
        soft_stop_pending=False,
        reason="below closing threshold",
    )


def complete_context_window_compaction(state: Mapping[str, Any] | ContextWindowState) -> dict[str, Any]:
    """Mark a context window as compacted after a summary boundary is recorded."""

    payload = state.to_dict() if isinstance(state, ContextWindowState) else dict(state)
    used_tokens = max(0, int(payload.get("used_tokens", 0) or 0))
    max_tokens = max(1, int(payload.get("max_tokens", 400000) or 400000))
    closing_tokens = max(1, int(payload.get("closing_tokens", int(max_tokens * 0.9)) or int(max_tokens * 0.9)))
    return _state(
        WINDOW_COMPACTED,
        used_tokens=used_tokens,
        max_tokens=max_tokens,
        closing_tokens=min(max_tokens, closing_tokens),
        soft_stop_pending=False,
        reason="context compaction complete",
    ).to_dict()


def context_window_prompt_source_content(state: Mapping[str, Any] | ContextWindowState) -> str:
    """Return concise prompt guidance for the current context-window phase."""

    payload = state.to_dict() if isinstance(state, ContextWindowState) else dict(state)
    phase = _normalize_phase(str(payload.get("phase", "") or WINDOW_OPEN))
    if phase == WINDOW_OPEN:
        return ""
    label = str(payload.get("label", "") or phase.capitalize())
    used_tokens = max(0, int(payload.get("used_tokens", 0) or 0))
    max_tokens = max(1, int(payload.get("max_tokens", 1) or 1))
    guidance = str(payload.get("prompt_guidance", "") or "").strip()
    soft_stop = bool(payload.get("soft_stop_pending", False))
    lines = [f"- Window: {label} ({used_tokens:,}/{max_tokens:,} tokens)"]
    if soft_stop:
        lines.append("- Soft stop: finish the active turn, then create a durable summary boundary before more new work.")
    if guidance:
        lines.append(f"- Guidance: {guidance}")
    return "\n".join(lines)


def _state(
    phase: str,
    *,
    used_tokens: int,
    max_tokens: int,
    closing_tokens: int,
    soft_stop_pending: bool,
    reason: str,
) -> ContextWindowState:
    if phase == WINDOW_CLOSING:
        return ContextWindowState(
            phase=phase,
            used_tokens=used_tokens,
            max_tokens=max_tokens,
            closing_tokens=closing_tokens,
            soft_stop_pending=soft_stop_pending,
            label="Closing",
            prompt_guidance=(
                "Avoid starting broad new work. Finish the current loop, preserve decisions and open tasks, "
                "then compact into a durable summary boundary."
            ),
            reason=reason,
        )
    if phase == WINDOW_COMPACTED:
        return ContextWindowState(
            phase=phase,
            used_tokens=used_tokens,
            max_tokens=max_tokens,
            closing_tokens=closing_tokens,
            soft_stop_pending=soft_stop_pending,
            label="Compacted",
            prompt_guidance="Use the compacted summary as the stable pre-boundary context.",
            reason=reason,
        )
    return ContextWindowState(
        phase=WINDOW_OPEN,
        used_tokens=used_tokens,
        max_tokens=max_tokens,
        closing_tokens=closing_tokens,
        soft_stop_pending=soft_stop_pending,
        label="Open",
        prompt_guidance="Normal context-window posture.",
        reason=reason,
    )


def _normalize_phase(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {WINDOW_OPEN, WINDOW_CLOSING, WINDOW_COMPACTED}:
        return normalized
    return WINDOW_OPEN
