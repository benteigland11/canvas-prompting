from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tool_invocation import ToolInvocationRequest
from src.tool_invocation import ToolInvocationRouter
from src.tool_invocation import ToolInvocationTarget


def read_file(path: str) -> str:
    return f"contents:{path}"


router = ToolInvocationRouter(
    (
        ToolInvocationTarget(
            tool_id="read_file",
            handler=read_file,
            target_kind="local",
            source_id="workspace",
            display_name="Read File",
            permission_mode="allow",
            metadata={"risk_level": "low"},
        ),
    )
)

result = router.invoke(ToolInvocationRequest(tool_id="read_file", args=("README.md",)))
print(result.status)
print(result.target_kind)
print(result.display_name)
print(result.output)
