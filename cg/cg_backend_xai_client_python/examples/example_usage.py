"""
Example usage of xAI Client.

This file must run and exit cleanly with no user input, no network calls,
and no external services or API keys. Use fake/hardcoded data to demonstrate the API.
The widget's own declared dependencies are fine — the validator installs them first.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.xai_client import TransportResponse
from src.xai_client import XAIClient
from src.xai_client import chat_function_tool
from src.xai_client import encode_data_uri
from src.xai_client import function_tool
from src.xai_client import mcp_tool
from src.xai_client import web_search_tool


class DemoTransport:
    def __init__(self) -> None:
        self._responses_call_count = 0

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        params=None,
        json_body=None,
        body=None,
        timeout=None,
    ):
        if url.endswith("/models"):
            payload = {"data": [{"id": "grok-4-1-fast-non-reasoning"}]}
        elif url.endswith("/chat/completions"):
            # Simulate a tool call response when tools are provided
            if json_body and json_body.get("tools"):
                payload = {
                    "id": "chatcmpl_demo_tools",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_demo_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_weather",
                                            "arguments": '{"location": "San Francisco"}',
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 25,
                        "total_tokens": 145,
                        "reasoning_tokens": 10,
                        "prompt_tokens_details": {"cached_tokens": 40},
                    },
                }
            else:
                payload = {
                    "id": "chatcmpl_demo_123",
                    "choices": [{"message": {"content": "xAI glue code can stay simple."}}],
                }
        elif url.endswith("/responses"):
            self._responses_call_count += 1
            # First call: return a function_call; second call: return text
            if self._responses_call_count == 1 and json_body and json_body.get("tools"):
                payload = {
                    "id": "resp_demo_tools",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call_resp_1",
                            "name": "get_temperature",
                            "arguments": '{"location": "NYC", "unit": "fahrenheit"}',
                        }
                    ],
                    "usage": {
                        "input_tokens": 80,
                        "output_tokens": 15,
                        "total_tokens": 95,
                        "input_tokens_details": {"cached_tokens": 20},
                        "output_tokens_details": {"reasoning_tokens": 5},
                    },
                }
            else:
                payload = {
                    "id": "resp_demo_123",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "The temperature in NYC is 59°F.",
                                }
                            ],
                        }
                    ],
                    "citations": [{"url": "https://weather.example.com", "snippet": "NYC 59°F"}],
                }
        elif url.endswith("/image-generation-models"):
            payload = {"data": [{"id": "grok-imagine-image"}]}
        elif url.endswith("/images/generations"):
            payload = {"data": [{"url": "https://cdn.example/generated.png"}]}
        elif url.endswith("/videos/generations"):
            payload = {"request_id": "vidreq_demo_123", "status": "queued"}
        elif url.endswith("/videos/vidreq_demo_123"):
            payload = {
                "request_id": "vidreq_demo_123",
                "status": "done",
                "video": {"url": "https://cdn.example/generated.mp4"},
            }
        elif url.endswith("/tokenize-text"):
            payload = {"token_ids": [{"token_id": 1}, {"token_id": 2}, {"token_id": 3}]}
        elif url.endswith("/tts/voices"):
            payload = {"voices": [{"voice_id": "alloy"}, {"voice_id": "verse"}]}
        else:
            payload = {"ok": True}
        if url.endswith("/tts"):
            return TransportResponse(
                status_code=200,
                headers={"Content-Type": "audio/wav"},
                body=b"RIFF....WAVE",
            )
        return TransportResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8"),
        )

    def stream(
        self,
        method,
        url,
        *,
        headers=None,
        params=None,
        json_body=None,
        body=None,
        timeout=None,
    ):
        yield b'data: {"choices":[{"delta":{"content":"stream "}}]}\n'
        yield b"\n"
        yield b'data: {"choices":[{"delta":{"content":"demo"}}]}\n'
        yield b"\n"
        yield b"data: [DONE]\n"
        yield b"\n"


client = XAIClient(api_key="demo-key", transport=DemoTransport())

# ── Basic usage ────────────────────────────────────────────────────────────

models = client.models.list()
chat = client.chat.completions_create(
    model="grok-4-1-fast-non-reasoning",
    messages=[{"role": "user", "content": "Why use this widget?"}],
)
image_models = client.models.list_image_generation_models()
image_response = client.images.generate(
    model="grok-imagine-image",
    prompt="An editorial illustration of clean API glue code.",
)
video_request = client.videos.generate(
    model="grok-imagine-video",
    prompt="A slow cinematic orbit around a brass compass.",
)
video_result = client.videos.get(client.videos.extract_request_id(video_request))
tokenized = client.tokenize.text(
    text="Count me",
    model="grok-4-1-fast-non-reasoning",
)
voices = client.voice.list_voices()
speech = client.voice.synthesize(
    voice="alloy",
    input="Read this aloud.",
    language="en",
    format="wav",
)
streamed = [
    event["choices"][0]["delta"]["content"]
    for event in client.chat.completions_stream(
        model="grok-4-1-fast-non-reasoning",
        messages=[{"role": "user", "content": "Stream a short sentence."}],
    )
]

print("Models:", [item["id"] for item in models["data"]])
print("Chat:", client.chat.extract_text(chat))
print("Image models:", [item["id"] for item in image_models["data"]])
print("Generated image URLs:", client.images.extract_urls(image_response))
print("Generated video URL:", client.videos.extract_video_url(video_result))
print("Data URI sample prefix:", encode_data_uri(b"abc", mime_type="image/png")[:22])
print("Token count:", client.tokenize.count_tokens(tokenized))
print("Voices:", client.voice.extract_voice_ids(voices))
print("Speech bytes:", len(speech))
print("Streamed:", "".join(streamed))

# ── Chat Completions with tool calling ─────────────────────────────────────

weather_tool = chat_function_tool(
    "get_weather",
    description="Get current weather for a location",
    parameters={
        "type": "object",
        "properties": {"location": {"type": "string", "description": "City name"}},
        "required": ["location"],
    },
)

tool_response = client.chat.completions_create(
    model="grok-4-1-fast-non-reasoning",
    messages=[{"role": "user", "content": "What's the weather in SF?"}],
    tools=[weather_tool],
)

tool_calls = client.chat.extract_tool_calls(tool_response)
usage = client.chat.extract_usage(tool_response)

print("\n--- Chat Completions Tool Calling ---")
print("Tool calls:", [(tc["name"], tc["arguments"]) for tc in tool_calls])
print("Usage:", usage)

# Build a tool result message for the next turn
if tool_calls:
    result_msg = client.chat.make_tool_result_message(
        tool_calls[0]["id"], '{"temp": 65, "unit": "fahrenheit"}'
    )
    print("Tool result message:", result_msg)

# ── Responses API with tool calling ────────────────────────────────────────

temp_tool = function_tool(
    "get_temperature",
    description="Get current temperature for a location",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["location"],
    },
)

resp_with_tools = client.responses.create(
    model="grok-4-1-fast-non-reasoning",
    input=[{"role": "user", "content": "What's the temperature in NYC?"}],
    tools=[temp_tool, web_search_tool()],
)

resp_tool_calls = client.responses.extract_tool_calls(resp_with_tools)
resp_usage = client.responses.extract_usage(resp_with_tools)

print("\n--- Responses API Tool Calling ---")
print("Tool calls:", [(tc["name"], tc["arguments"]) for tc in resp_tool_calls])
print("Usage:", resp_usage)

# Send tool result back and get final answer
if resp_tool_calls:
    tool_result = client.responses.make_tool_result(
        resp_tool_calls[0]["call_id"], '{"temperature": 59, "unit": "fahrenheit"}'
    )
    followup = client.responses.create(
        model="grok-4-1-fast-non-reasoning",
        input=[tool_result],
        previous_response_id=resp_with_tools["id"],
        tools=[temp_tool],
    )
    print("Final answer:", client.responses.extract_text(followup))
    print("Citations:", client.responses.extract_citations(followup))

# ── Tool builder examples ──────────────────────────────────────────────────

print("\n--- Tool Builders ---")
print("MCP tool:", mcp_tool("https://mcp.example.com/mcp", "my-server", allowed_tools=["search"]))
