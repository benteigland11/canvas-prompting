"""Reusable facade for composing LLM context bundle widgets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from cg.data_context_compaction_plan_python.src.context_compaction_plan import build_context_compaction_plan
from cg.data_context_compaction_plan_python.src.context_compaction_plan import build_context_items
from cg.universal_context_payload_projection_python.src.context_payload_projection import project_payload_content
from cg.universal_context_retention_policy_python.src.context_retention_policy import RetentionPolicyConfig
from cg.universal_context_retention_policy_python.src.context_retention_policy import decide_retention_many
from cg.universal_llm_context_bundle_python.src.llm_context_bundle import LLMContextBundle
from cg.universal_llm_context_bundle_python.src.llm_context_bundle import LLMContextBundleBuilder
from cg.universal_llm_context_bundle_python.src.llm_context_bundle import LLMContextToolCall

BLUEPRINT_ID = "bp-llm-context-bundle-python"


@dataclass(frozen=True)
class LlmContextBundleSurface:
    """One computed model-facing context surface."""

    bundle: LLMContextBundle
    context_management: dict[str, object]
    profile: str
    model: str
    provider: str
    target_id: str
    tool_ids: frozenset[str]
    message_count: int

    def tokenization_payload(self) -> dict[str, object]:
        return self.bundle.to_dict()

    def tokenization_text(self) -> str:
        return json.dumps(self.tokenization_payload(), ensure_ascii=False, separators=(",", ":"))

    def tokenization_payload_hash(self) -> str:
        return hashlib.sha256(self.tokenization_text().encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "blueprint_id": BLUEPRINT_ID,
            "profile": self.profile,
            "model": self.model,
            "provider": self.provider,
            "target_id": self.target_id,
            "tool_ids": sorted(self.tool_ids),
            "message_count": self.message_count,
            "context_management": dict(self.context_management),
            "bundle": self.bundle.to_dict(),
            "tokenization_payload_hash": self.tokenization_payload_hash(),
        }


def blueprint_summary() -> dict[str, object]:
    """Return the stable app-facing intent for this blueprint."""

    return {
        "blueprint_id": BLUEPRINT_ID,
        "purpose": "Compose widgets for model-facing LLM context bundle construction.",
        "surface": "LlmContextBundleSurface",
        "dependencies": (
            "data-context-compaction-plan-python",
            "universal-context-payload-projection-python",
            "universal-context-retention-policy-python",
            "universal-context-usage-tracker-python",
            "universal-agent-context-window-policy-python",
            "universal-agent-compaction-summary-python",
            "universal-context-optimization-ledger-python",
            "universal-context-optimization-report-python",
            "universal-llm-context-bundle-python",
        ),
    }


def build_context_management_plan(
    *,
    items: tuple[Any, ...] | list[Any],
    decisions: tuple[Any, ...] | list[Any] | None = None,
    retention_config: RetentionPolicyConfig | None = None,
) -> dict[str, object]:
    """Build a keep/summarize/drop plan from generic context items."""

    resolved_items = tuple(items)
    resolved_decisions = tuple(decisions) if decisions is not None else tuple(
        decision.to_dict()
        for decision in decide_retention_many(
            tuple(_retention_payload(item) for item in resolved_items),
            config=retention_config,
        )
    )
    return build_context_compaction_plan(resolved_items, decisions=resolved_decisions).to_dict()


def build_llm_context_bundle_surface(
    *,
    system_prompt: str,
    conversation_messages: tuple[Any, ...] | list[Any],
    tools: tuple[Any, ...] | list[Any] = (),
    profile: str = "master",
    model: str = "unset",
    provider: str = "",
    target_id: str = "",
    context_management: dict[str, object] | None = None,
) -> LlmContextBundleSurface:
    """Build a provider-neutral LLM context surface from app-owned records."""

    resolved_context_management = dict(context_management or {})
    builder = LLMContextBundleBuilder()
    builder.set_system_prompt(system_prompt)
    message_count = 0
    for message in tuple(conversation_messages):
        if _add_message_to_builder(builder, message, context_management=resolved_context_management):
            message_count += 1

    tool_ids: list[str] = []
    for tool in tuple(tools):
        tool_id = str(_value(tool, "tool_id") or "")
        display_name = str(_value(tool, "display_name") or tool_id)
        description = str(_value(tool, "description") or "")
        if not tool_id or not display_name or not description:
            continue
        parameters = _mapping(_value(tool, "parameters") or _value(tool, "schema"))
        metadata = _mapping(_value(tool, "metadata"))
        builder.add_function_tool(
            tool_id=tool_id,
            display_name=display_name,
            description=description,
            parameters=parameters,
            metadata=metadata,
        )
        tool_ids.append(tool_id)

    metadata = {"profile": profile, "model": model}
    if provider.strip():
        metadata["provider"] = provider.strip()
    if target_id.strip():
        metadata["target_id"] = target_id.strip()
    if resolved_context_management:
        metadata["context_management"] = dict(resolved_context_management)
    builder.set_metadata(**metadata)
    return LlmContextBundleSurface(
        bundle=builder.build(),
        context_management=resolved_context_management,
        profile=profile,
        model=model,
        provider=provider,
        target_id=target_id,
        tool_ids=frozenset(tool_ids),
        message_count=message_count,
    )


def _add_message_to_builder(
    builder: LLMContextBundleBuilder,
    message: Any,
    *,
    context_management: dict[str, object],
) -> bool:
    role = str(_value(message, "role") or "").strip().lower()
    content = str(_value(message, "content") or "")
    metadata = _mapping(_value(message, "metadata"))
    tool_calls = _tool_calls_from_metadata(metadata)
    projection = _projection_for_message(message, context_management)
    projected = project_payload_content(
        content,
        projection=projection,
        metadata=metadata,
        fallback_name=str(metadata.get("tool_name", "") or metadata.get("name", "") or role or "message"),
        fallback_status=str(projection.get("status", "") or _value(message, "status") or "complete"),
    )
    content = projected.content
    if not role:
        return False
    if not content.strip() and not (role == "assistant" and tool_calls):
        return False

    bundle_metadata = {
        "message_id": str(_value(message, "message_id") or ""),
        "status": str(_value(message, "status") or ""),
    }
    if metadata.get("context_projection"):
        bundle_metadata["context_projection"] = metadata["context_projection"]
    if projection:
        bundle_metadata["context_projection"] = projection

    builder.add_message(
        role=role,
        content=content,
        name=str(metadata.get("name", "") or metadata.get("tool_name", "")),
        tool_call_id=str(metadata.get("tool_call_id", "")),
        tool_calls=tool_calls,
        metadata=bundle_metadata,
    )
    return True


def _projection_for_message(message: Any, context_management: dict[str, object]) -> dict[str, Any]:
    message_id = str(_value(message, "message_id") or "")
    if not message_id:
        return {}
    decisions = context_management.get("decisions", ())
    if not isinstance(decisions, (tuple, list)):
        return {}
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if str(decision.get("item_id", "") or "") == message_id:
            return dict(decision)
    return {}


def _tool_calls_from_metadata(metadata: dict[str, Any]) -> tuple[LLMContextToolCall, ...]:
    raw_calls = metadata.get("tool_calls", ())
    if not isinstance(raw_calls, (tuple, list)):
        return ()
    calls: list[LLMContextToolCall] = []
    for raw_call in raw_calls:
        if not isinstance(raw_call, dict):
            continue
        call_id = str(raw_call.get("id", "") or raw_call.get("call_id", "") or "").strip()
        name = str(raw_call.get("name", "") or raw_call.get("tool_name", "") or "").strip()
        if not call_id or not name:
            continue
        calls.append(
            LLMContextToolCall(
                id=call_id,
                name=name,
                arguments=str(raw_call.get("arguments", "") or ""),
                metadata=dict(raw_call.get("metadata", {}) or {}),
            )
        )
    return tuple(calls)


def _retention_payload(item: Any) -> dict[str, object]:
    return {
        "item_id": _value(item, "item_id"),
        "item_type": _value(item, "item_type"),
        "role": _value(item, "role"),
        "status": _value(item, "status"),
        "name": _value(item, "name"),
        "token_count": _value(item, "token_count"),
        "age_index": _value(item, "age_index"),
        "metadata": _mapping(_value(item, "metadata")),
    }


def _value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key, "")
    return getattr(value, key, "")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


__all__ = [
    "BLUEPRINT_ID",
    "LLMContextBundle",
    "LlmContextBundleSurface",
    "RetentionPolicyConfig",
    "blueprint_summary",
    "build_context_items",
    "build_context_management_plan",
    "build_llm_context_bundle_surface",
]
