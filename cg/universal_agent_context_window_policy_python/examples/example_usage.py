from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent_context_window_policy import ContextWindowPolicyConfig
from src.agent_context_window_policy import context_window_prompt_source_content
from src.agent_context_window_policy import evaluate_context_window


state = evaluate_context_window(
    used_tokens=360000,
    config=ContextWindowPolicyConfig(max_tokens=400000, closing_ratio=0.9),
)

print(state.to_dict()["label"])
print(context_window_prompt_source_content(state).splitlines()[0])
