from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.context_compaction_plan import build_context_compaction_plan
from src.context_compaction_plan import build_context_items
from src.context_compaction_plan import plan_summary_text


items = build_context_items(messages=({"message_id": "m1", "role": "user", "content": "hello"},))
plan = build_context_compaction_plan(items, decisions=({"item_id": "m1", "decision": "keep", "reason": "recent"},))
print(plan_summary_text(plan))
