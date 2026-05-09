"""Example usage of the llm-context-bundle blueprint."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.llm_context_bundle import build_llm_context_bundle_surface


if __name__ == "__main__":
    surface = build_llm_context_bundle_surface(
        system_prompt="Be concise.",
        conversation_messages=[
            {
                "message_id": "msg_1",
                "role": "user",
                "content": "Summarize the current task.",
                "status": "complete",
                "metadata": {},
            }
        ],
        tools=[
            {
                "tool_id": "read_file",
                "display_name": "Read File",
                "description": "Read a workspace file.",
                "parameters": {"type": "object"},
            }
        ],
        model="example-model",
    )
    print(surface.to_dict()["blueprint_id"])
