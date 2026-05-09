from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.context_retention_policy import RetentionItem
from src.context_retention_policy import decide_retention


item = RetentionItem("message_1", "message", role="assistant", token_count=800, age_index=12)
print(decide_retention(item).to_dict())
