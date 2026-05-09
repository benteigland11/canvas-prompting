import pytest
import asyncio
from unittest.mock import patch
from src.grok_adapter import (
    GrokAdapter, ChatRequest, Message, FunctionTool, StreamEvent, StreamStart, ContentDelta, StreamEnd
)

import os

@pytest.fixture
def adapter():
    with patch.dict(os.environ, {"XAI_API_KEY": "dummy"}):
        return GrokAdapter()

def test_supports(adapter):
    assert adapter.supports("function_tools") is True
    assert adapter.supports("streaming") is True
    assert adapter.supports("unknown") is False

def test_build_payload(adapter):
    req = ChatRequest(
        model="grok-beta",
        messages=[
            Message(role="system", content="System msg"),
            Message(role="user", content="User msg", name="user1"),
            Message(role="tool", content="Tool result", tool_call_id="call_123")
        ],
        temperature=0.7,
        max_tokens=100,
        tools=[
            FunctionTool(name="my_tool", description="A tool", parameters={"type": "object"})
        ],
        tool_choice="auto"
    )
    payload = adapter._build_payload(req)
    assert payload["model"] == "grok-beta"
    assert payload["temperature"] == 0.7
    assert payload["max_tokens"] == 100
    assert payload["tool_choice"] == "auto"
    assert len(payload["messages"]) == 3
    assert payload["messages"][0] == {"role": "system", "content": "System msg"}
    assert payload["messages"][1] == {"role": "user", "content": "User msg", "name": "user1"}
    assert payload["messages"][2] == {"role": "tool", "content": "Tool result", "tool_call_id": "call_123"}
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["type"] == "function"
    assert payload["tools"][0]["function"]["name"] == "my_tool"

@pytest.mark.asyncio
async def test_chat(adapter):
    req = ChatRequest(model="grok-beta", messages=[Message(role="user", content="Hello")])
    
    # Mock the synchronous XAIClient call
    mock_raw_response = {
        "model": "grok-beta",
        "choices": [{"finish_reason": "stop"}],
    }
    
    with patch.object(adapter.client.chat, 'completions_create', return_value=mock_raw_response):
        with patch.object(adapter.client.chat, 'extract_text', return_value="Hi there!"):
            with patch.object(adapter.client.chat, 'extract_usage', return_value={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}):
                with patch.object(adapter.client.chat, 'extract_tool_calls', return_value=[]):
                    response = await adapter.chat(req)
                    assert response.content == "Hi there!"
                    assert response.usage.input_tokens == 10
                    assert response.usage.output_tokens == 5
                    assert response.stop_reason == "stop"
                    assert response.model == "grok-beta"
                    assert response.tool_calls is None

@pytest.mark.asyncio
async def test_stream_chat(adapter):
    req = ChatRequest(model="grok-beta", messages=[Message(role="user", content="Hello")])
    
    def mock_stream(**kwargs):
        yield {"choices": [{"delta": {"content": "Hi"}}]}
        yield {"choices": [{"delta": {"content": " there"}}]}
        yield {"choices": [{"finish_reason": "stop"}]}
    
    with patch.object(adapter.client.chat, 'completions_stream', side_effect=mock_stream):
        events = []
        async for event in adapter.stream_chat(req):
            events.append(event)
            
        assert len(events) == 4
        assert isinstance(events[0], StreamStart)
        assert isinstance(events[1], ContentDelta)
        assert events[1].text == "Hi"
        assert isinstance(events[2], ContentDelta)
        assert events[2].text == " there"
        assert isinstance(events[3], StreamEnd)
        assert events[3].stop_reason == "stop"
