from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent_tool_loop import AgentToolLoop
from src.agent_tool_loop import ModelTurn
from src.agent_tool_loop import ToolRequest
from src.agent_tool_loop import ToolResult


loop = AgentToolLoop()

print(loop.begin())

first_decision = loop.receive_model_turn(
    ModelTurn(
        content="I need to inspect a file before answering.",
        tool_requests=(
            ToolRequest(
                request_id="req_1",
                tool_name="read_file",
                payload={"path": "notes.txt"},
            ),
        ),
    )
)
print(first_decision)

second_decision = loop.receive_tool_results(
    (
        ToolResult(
            request_id="req_1",
            tool_name="read_file",
            status="success",
            output="file contents",
        ),
    )
)
print(second_decision)

final_decision = loop.receive_model_turn(
    ModelTurn(content="I checked the file. Here is the answer.")
)
print(final_decision)
