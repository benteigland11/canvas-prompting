from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


WIDGET_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = WIDGET_ROOT / "src" / "agent_tool_loop.py"
SPEC = importlib.util.spec_from_file_location("widget_agent_tool_loop", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["widget_agent_tool_loop"] = MODULE
SPEC.loader.exec_module(MODULE)

AgentToolLoop = MODULE.AgentToolLoop
ModelTurn = MODULE.ModelTurn
ToolLoopConfig = MODULE.ToolLoopConfig
ToolRequest = MODULE.ToolRequest
ToolResult = MODULE.ToolResult


def test_begin_requests_initial_model_turn() -> None:
    loop = AgentToolLoop()

    decision = loop.begin()

    assert decision.kind == "request_model"
    assert decision.reason == "begin_loop"
    assert decision.iteration_index == 0


def test_model_turn_without_tools_completes_loop() -> None:
    loop = AgentToolLoop()

    decision = loop.receive_model_turn(ModelTurn(content="Final answer"))

    assert decision.kind == "complete"
    assert decision.final_content == "Final answer"
    assert decision.reason == "model_returned_final_content"


def test_model_turn_with_tools_requests_execution() -> None:
    loop = AgentToolLoop()
    request = ToolRequest(request_id="req_1", tool_name="read_file", payload={"path": "a.txt"})

    decision = loop.receive_model_turn(ModelTurn(content="Need a file", tool_requests=(request,)))

    assert decision.kind == "execute_tools"
    assert decision.reason == "model_requested_tools"
    assert decision.tool_requests == (request,)


def test_tool_results_continue_loop_when_successful() -> None:
    loop = AgentToolLoop()
    request = ToolRequest(request_id="req_1", tool_name="read_file")
    loop.receive_model_turn(ModelTurn(content="Need a file", tool_requests=(request,)))

    decision = loop.receive_tool_results(
        (ToolResult(request_id="req_1", tool_name="read_file", status="success", output="ok"),)
    )

    assert decision.kind == "request_model"
    assert decision.reason == "tool_results_ready"
    assert decision.iteration_index == 1


def test_tool_failure_halts_by_default() -> None:
    loop = AgentToolLoop()
    request = ToolRequest(request_id="req_1", tool_name="read_file")
    loop.receive_model_turn(ModelTurn(content="Need a file", tool_requests=(request,)))

    decision = loop.receive_tool_results(
        (ToolResult(request_id="req_1", tool_name="read_file", status="error", error="missing"),)
    )

    assert decision.kind == "halt"
    assert decision.reason == "tool_failure"


def test_tool_failure_can_continue_when_configured() -> None:
    loop = AgentToolLoop(ToolLoopConfig(continue_on_tool_failure=True))
    request = ToolRequest(request_id="req_1", tool_name="read_file")
    loop.receive_model_turn(ModelTurn(content="Need a file", tool_requests=(request,)))

    decision = loop.receive_tool_results(
        (ToolResult(request_id="req_1", tool_name="read_file", status="permission_required"),)
    )

    assert decision.kind == "request_model"
    assert decision.reason == "tool_results_ready_after_failure"


def test_rejects_new_model_turn_while_waiting_for_tool_results() -> None:
    loop = AgentToolLoop()
    request = ToolRequest(request_id="req_1", tool_name="read_file")
    loop.receive_model_turn(ModelTurn(content="Need a file", tool_requests=(request,)))

    with pytest.raises(RuntimeError, match="awaiting tool results"):
        loop.receive_model_turn(ModelTurn(content="Second answer"))


def test_rejects_tool_results_before_model_requests_tools() -> None:
    loop = AgentToolLoop()

    with pytest.raises(RuntimeError, match="before the model requests tools"):
        loop.receive_tool_results(
            (ToolResult(request_id="req_1", tool_name="read_file", status="success"),)
        )


def test_halts_when_model_turn_exceeds_max_iterations() -> None:
    loop = AgentToolLoop(ToolLoopConfig(max_iterations=1))
    request = ToolRequest(request_id="req_1", tool_name="read_file")

    first = loop.receive_model_turn(ModelTurn(content="Need a file", tool_requests=(request,)))
    assert first.kind == "execute_tools"
    second = loop.receive_tool_results(
        (ToolResult(request_id="req_1", tool_name="read_file", status="success"),)
    )
    assert second.kind == "halt"
    assert second.reason == "max_iterations_reached_after_tools"


def test_halts_on_duplicate_model_turn_when_limit_configured() -> None:
    loop = AgentToolLoop(ToolLoopConfig(max_duplicate_model_turns=1))
    first = loop.receive_model_turn(ModelTurn(content="same"))
    assert first.kind == "complete"

    second_loop = AgentToolLoop(ToolLoopConfig(max_duplicate_model_turns=2, max_iterations=10))
    request = ToolRequest(request_id="r1", tool_name="read_file", payload={"p": 1})
    turn = ModelTurn(content="dup", tool_requests=(request,))
    d1 = second_loop.receive_model_turn(turn)
    assert d1.kind == "execute_tools"
    second_loop.receive_tool_results(
        (ToolResult(request_id="r1", tool_name="read_file", status="success"),)
    )
    d2 = second_loop.receive_model_turn(turn)
    assert d2.kind == "execute_tools"
    second_loop.receive_tool_results(
        (ToolResult(request_id="r1", tool_name="read_file", status="success"),)
    )
    d3 = second_loop.receive_model_turn(turn)
    assert d3.kind == "halt"
    assert d3.reason == "duplicate_model_turn"


def test_halts_on_duplicate_tool_request_when_limit_configured() -> None:
    loop = AgentToolLoop(
        ToolLoopConfig(max_duplicate_tool_request_attempts=1, max_iterations=10)
    )
    request = ToolRequest(request_id="r1", tool_name="read_file", payload={"p": 1})

    first = loop.receive_model_turn(ModelTurn(content="one", tool_requests=(request,)))
    assert first.kind == "execute_tools"
    loop.receive_tool_results(
        (ToolResult(request_id="r1", tool_name="read_file", status="success"),)
    )

    second = loop.receive_model_turn(ModelTurn(content="two", tool_requests=(request,)))
    assert second.kind == "halt"
    assert second.reason == "duplicate_tool_request"


def test_halts_on_repeated_tool_failure_when_limit_configured() -> None:
    loop = AgentToolLoop(
        ToolLoopConfig(
            continue_on_tool_failure=True,
            max_repeated_tool_failures=1,
            max_iterations=10,
        )
    )
    request = ToolRequest(request_id="r1", tool_name="read_file")

    loop.receive_model_turn(ModelTurn(content="a", tool_requests=(request,)))
    loop.receive_tool_results(
        (ToolResult(request_id="r1", tool_name="read_file", status="error", error="boom"),)
    )
    loop.receive_model_turn(ModelTurn(content="b", tool_requests=(request,)))
    decision = loop.receive_tool_results(
        (ToolResult(request_id="r1", tool_name="read_file", status="error", error="boom"),)
    )
    assert decision.kind == "halt"
    assert decision.reason == "repeated_tool_failure"


def test_halts_when_model_turn_has_no_progress() -> None:
    loop = AgentToolLoop(ToolLoopConfig(require_progress=True))
    decision = loop.receive_model_turn(ModelTurn(content="   "))
    assert decision.kind == "halt"
    assert decision.reason == "no_progress_model_turn"


def test_reset_clears_iterations_and_waiting_flag() -> None:
    loop = AgentToolLoop()
    request = ToolRequest(request_id="r1", tool_name="read_file")
    loop.receive_model_turn(ModelTurn(content="hi", tool_requests=(request,)))
    assert loop.current_iteration_index() == 1

    loop.reset()
    assert loop.current_iteration_index() == 0
    assert loop.iterations() == ()
    decision = loop.receive_model_turn(ModelTurn(content="fresh"))
    assert decision.kind == "complete"
