from src.context_retention_policy import DECISION_DROP
from src.context_retention_policy import DECISION_KEEP
from src.context_retention_policy import DECISION_SUMMARIZE
from src.context_retention_policy import RetentionItem
from src.context_retention_policy import RetentionPolicyConfig
from src.context_retention_policy import decide_retention
from src.context_retention_policy import decide_retention_many
from src.context_retention_policy import decision_counts


def test_decide_retention_keeps_recent_items() -> None:
    decision = decide_retention(RetentionItem("m1", "message", role="user", token_count=200, age_index=0))

    assert decision.decision == DECISION_KEEP
    assert decision.reason == "recent"


def test_decide_retention_summarizes_old_large_items() -> None:
    decision = decide_retention(
        RetentionItem("m1", "message", role="assistant", token_count=900, age_index=9),
        config=RetentionPolicyConfig(keep_recent_count=2, summarize_after_count=4, drop_after_count=20),
    )

    assert decision.decision == DECISION_SUMMARIZE
    assert decision.reason == "old_large"


def test_decide_retention_drops_old_successful_tool_results() -> None:
    decision = decide_retention(
        RetentionItem("t1", "tool_result", status="success", token_count=100, age_index=30),
        config=RetentionPolicyConfig(keep_recent_count=2, drop_successful_tool_results_after_count=10),
    )

    assert decision.decision == DECISION_DROP
    assert decision.reason == "old_successful_tool_result"


def test_decide_retention_keeps_system_and_streaming_items() -> None:
    system = decide_retention(RetentionItem("s1", "message", role="system", age_index=100))
    streaming = decide_retention(RetentionItem("a1", "message", role="assistant", status="streaming", age_index=100))

    assert system.decision == DECISION_KEEP
    assert streaming.decision == DECISION_KEEP


def test_decision_counts_counts_all_decisions() -> None:
    decisions = decide_retention_many(
        (
            {"item_id": "a", "item_type": "message", "age_index": 0},
            {"item_id": "b", "item_type": "message", "age_index": 10, "token_count": 1000},
            {"item_id": "c", "item_type": "message", "age_index": 100, "token_count": 1000},
        ),
        config=RetentionPolicyConfig(keep_recent_count=1, summarize_after_count=2, drop_after_count=50),
    )

    assert decision_counts(decisions) == {"keep": 1, "summarize": 1, "drop": 1}
