from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm_context_bundle import LLMContextBundleBuilder, LLMContextToolCall


def main() -> None:
    builder = LLMContextBundleBuilder()
    builder.set_system_prompt("You are Jax.")

    # App-defined function tool — the app executes the call and returns a result.
    builder.add_function_tool(
        tool_id="read_file",
        display_name="Read File",
        description="Read a file from the current workspace.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        metadata={"permission_mode": "ask"},
    )

    # Vendor-hosted server tool — the provider runs it, results stream inline.
    builder.add_server_tool(
        tool_id="web_search",
        display_name="Web Search",
        description="Vendor-hosted web search.",
        config={"max_results": 5},
    )

    # A multi-turn tool-use conversation.
    builder.add_message(role="user", content="What's in AGENTS.md?")
    builder.add_assistant_tool_call_message(
        tool_calls=(
            LLMContextToolCall(
                id="call_1",
                name="read_file",
                arguments='{"path": "AGENTS.md"}',
            ),
        ),
    )
    builder.add_tool_result_message(
        tool_call_id="call_1",
        content="# AGENTS.md\n\nThis is the agents doc.",
        name="read_file",
    )
    builder.add_message(role="assistant", content="The file describes the agents.")

    builder.set_metadata(profile="master")

    bundle = builder.build()
    print(bundle.to_json())


if __name__ == "__main__":
    main()
