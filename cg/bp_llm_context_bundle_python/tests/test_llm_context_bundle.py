"""Tests for the llm-context-bundle blueprint API surface."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.llm_context_bundle import BLUEPRINT_ID
from src.llm_context_bundle import blueprint_summary
from src.llm_context_bundle import build_context_items
from src.llm_context_bundle import build_context_management_plan
from src.llm_context_bundle import build_llm_context_bundle_surface


def test_blueprint_summary_names_context_surface():
    summary = blueprint_summary()

    assert summary["blueprint_id"] == BLUEPRINT_ID
    assert "context bundle" in summary["purpose"].lower()
    assert summary["surface"] == "LlmContextBundleSurface"


def test_build_surface_projects_messages_and_tools():
    context_management = {
        "decisions": [
            {
                "item_id": "msg_1",
                "decision": "drop",
                "reason": "old",
                "token_count": 42,
                "metadata": {"name": "old result", "status": "success"},
            }
        ]
    }

    surface = build_llm_context_bundle_surface(
        system_prompt="Be brief.",
        conversation_messages=[
            {
                "message_id": "msg_1",
                "role": "tool",
                "content": "large payload",
                "status": "complete",
                "metadata": {"tool_name": "read_file"},
            },
            {
                "message_id": "msg_2",
                "role": "user",
                "content": "continue",
                "status": "complete",
                "metadata": {},
            },
        ],
        tools=[
            {
                "tool_id": "read_file",
                "display_name": "Read File",
                "description": "Read a workspace file.",
                "parameters": {"type": "object"},
            }
        ],
        model="grok-test",
        provider="remote",
        target_id="target-test",
        context_management=context_management,
    )

    assert surface.message_count == 2
    assert surface.tool_ids == frozenset({"read_file"})
    assert surface.bundle.metadata["context_management"] == context_management
    assert surface.bundle.messages[0].content.startswith("[content omitted:")
    assert surface.bundle.messages[1].content == "continue"
    assert surface.bundle.function_tools[0].tool_id == "read_file"
    assert surface.tokenization_payload_hash()


def test_build_context_management_plan_decides_retention():
    items = build_context_items(
        messages=[
            {"message_id": "msg_1", "role": "user", "content": "hello"},
            {"message_id": "msg_2", "role": "assistant", "content": "old text " * 200},
        ]
    )

    plan = build_context_management_plan(items=items)

    assert plan["decision_counts"]["keep"] >= 1
    assert len(plan["decisions"]) == 2
    assert plan["input_tokens"] > 0
