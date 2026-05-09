from pathlib import Path
import sys


sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.context_payload_projection import project_payload_content


payload = "\n".join(f"result row {index}" for index in range(40))
projection = {
    "decision": "summarize",
    "reason": "old_large",
    "name": "query_result",
    "status": "success",
    "token_count": 1600,
}

result = project_payload_content(payload, projection=projection, max_summary_chars=160)
print(result.content)
