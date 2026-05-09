from dataclasses import dataclass

from src.context_compaction_plan import build_context_compaction_plan
from src.context_compaction_plan import build_context_items
from src.context_compaction_plan import plan_summary_text


@dataclass(frozen=True)
class Message:
    message_id: str
    role: str
    content: str
    status: str = "complete"


def test_build_context_items_combines_messages_and_tool_results() -> None:
    items = build_context_items(
        messages=(Message("m1", "user", "hello"),),
        result_events=(
            {
                "sequence": 1,
                "result_name": "read_file",
                "status": "success",
                "source_text": "payload",
                "estimated_tokens": 9,
            },
        ),
    )

    assert [item.item_type for item in items] == ["message", "tool_result"]
    assert items[0].item_id == "m1"
    assert items[1].item_id == "tool_result_1"
    assert items[1].token_count == 9


def test_build_context_compaction_plan_counts_decisions_and_tokens() -> None:
    items = build_context_items(
        messages=(Message("m1", "user", "hello"), Message("m2", "assistant", "x" * 1000)),
    )
    decisions = (
        {"item_id": "m1", "decision": "keep", "reason": "recent"},
        {"item_id": "m2", "decision": "summarize", "reason": "old_large"},
    )

    plan = build_context_compaction_plan(items, decisions=decisions)

    assert plan.decision_counts == {"keep": 1, "summarize": 1, "drop": 0}
    assert plan.input_tokens == items[0].token_count + items[1].token_count
    assert plan.keep_tokens == items[0].token_count
    assert plan.summarize_tokens == items[1].token_count
    assert "summarize 1" in plan_summary_text(plan)


def test_build_context_compaction_plan_preserves_decision_projection_metadata() -> None:
    items = build_context_items(
        messages=(Message("m1", "tool", "raw payload"),),
    )
    plan = build_context_compaction_plan(
        items,
        decisions=(
            {
                "item_id": "m1",
                "decision": "summarize",
                "reason": "linked_tool_result_summarize",
                "token_count": 1200,
                "metadata": {
                    "name": "read_file",
                    "status": "success",
                    "summary_text": "Distilled facts.",
                },
            },
        ),
    )

    decision = plan.to_dict()["decisions"][0]
    assert decision["token_count"] == 1200
    assert decision["metadata"]["name"] == "read_file"
    assert decision["metadata"]["status"] == "success"
    assert decision["metadata"]["summary_text"] == "Distilled facts."
