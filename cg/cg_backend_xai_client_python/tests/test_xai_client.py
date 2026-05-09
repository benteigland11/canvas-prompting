import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.xai_client import TransportResponse
from src.xai_client import UrllibTransport
from src.xai_client import XAIAPIError
from src.xai_client import XAIClient
from src.xai_client import XAIConfigurationError
from src.xai_client import _append_query_params
from src.xai_client import chat_function_tool
from src.xai_client import code_interpreter_tool
from src.xai_client import encode_data_uri
from src.xai_client import file_search_tool
from src.xai_client import function_tool
from src.xai_client import mcp_tool
from src.xai_client import web_search_tool
from src.xai_client import x_search_tool


class FakeTransport:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.stream_requests: list[dict[str, object]] = []
        self.response_map: dict[tuple[str, str], TransportResponse] = {}
        self.stream_lines: list[bytes] = []

    def add_json_response(
        self,
        method: str,
        url: str,
        payload: dict[str, object],
        *,
        status_code: int = 200,
    ) -> None:
        self.response_map[(method.upper(), url)] = TransportResponse(
            status_code=status_code,
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8"),
        )

    def add_bytes_response(self, method: str, url: str, payload: bytes) -> None:
        self.response_map[(method.upper(), url)] = TransportResponse(
            status_code=200,
            headers={},
            body=payload,
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        headers=None,
        params=None,
        json_body=None,
        body=None,
        timeout=None,
    ) -> TransportResponse:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "json_body": json_body,
                "body": body,
                "timeout": timeout,
            }
        )
        final_url = _append_query_params(url, params)
        return self.response_map[(method.upper(), final_url)]

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers=None,
        params=None,
        json_body=None,
        body=None,
        timeout=None,
    ):
        self.stream_requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "json_body": json_body,
                "body": body,
                "timeout": timeout,
            }
        )
        yield from self.stream_lines


def make_client(transport: FakeTransport) -> XAIClient:
    return XAIClient(api_key="test-key", transport=transport)


def test_requires_api_key() -> None:
    with pytest.raises(XAIConfigurationError, match="API key is required"):
        XAIClient(api_key=None, transport=FakeTransport())


def test_client_forwards_timeout_to_transport() -> None:
    transport = FakeTransport()
    transport.add_json_response("GET", "https://api.x.ai/v1/models", {"data": []})
    client = XAIClient(api_key="test-key", transport=transport, timeout=123.0)

    client.models.list()

    assert transport.requests[0]["timeout"] == 123.0


def test_client_forwards_timeout_to_stream() -> None:
    transport = FakeTransport()
    transport.stream_lines = [b"data: [DONE]\n", b"\n"]
    client = XAIClient(api_key="test-key", transport=transport, timeout=77.5)

    list(client.chat.completions_stream(model="grok-4", messages=[]))

    assert transport.stream_requests[0]["timeout"] == 77.5


def test_client_allows_none_timeout() -> None:
    transport = FakeTransport()
    transport.add_json_response("GET", "https://api.x.ai/v1/models", {"data": []})
    client = XAIClient(api_key="test-key", transport=transport, timeout=None)

    client.models.list()

    assert transport.requests[0]["timeout"] is None


def test_lists_and_gets_models() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/models",
        {"data": [{"id": "grok-4-fast-non-reasoning"}]},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/models/grok-4-fast-non-reasoning",
        {"id": "grok-4-fast-non-reasoning"},
    )
    client = make_client(transport)

    listed = client.models.list()
    fetched = client.models.get("grok-4-fast-non-reasoning")

    assert listed["data"][0]["id"] == "grok-4-fast-non-reasoning"
    assert fetched["id"] == "grok-4-fast-non-reasoning"
    assert transport.requests[0]["headers"]["Authorization"] == "Bearer test-key"


def test_lists_language_models() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/language-models",
        {"data": [{"id": "grok-4-1-fast-non-reasoning"}]},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/language-models/grok-4-1-fast-non-reasoning",
        {"id": "grok-4-1-fast-non-reasoning"},
    )
    client = make_client(transport)

    listed = client.models.list_language_models()
    fetched = client.models.get_language_model("grok-4-1-fast-non-reasoning")

    assert listed["data"][0]["id"] == "grok-4-1-fast-non-reasoning"
    assert fetched["id"] == "grok-4-1-fast-non-reasoning"


def test_lists_and_gets_image_generation_models() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/image-generation-models",
        {"data": [{"id": "grok-imagine-image"}]},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/image-generation-models/grok-imagine-image",
        {"id": "grok-imagine-image"},
    )
    client = make_client(transport)

    listed = client.models.list_image_generation_models()
    fetched = client.models.get_image_generation_model("grok-imagine-image")

    assert listed["data"][0]["id"] == "grok-imagine-image"
    assert fetched["id"] == "grok-imagine-image"


def test_creates_chat_completion() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/chat/completions",
        {"id": "chatcmpl_123", "choices": [{"message": {"content": "hello"}}]},
    )
    client = make_client(transport)

    result = client.chat.completions_create(
        model="grok-4-1-fast-non-reasoning",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result["id"] == "chatcmpl_123"
    assert transport.requests[0]["json_body"]["model"] == "grok-4-1-fast-non-reasoning"
    assert client.chat.extract_text(result) == "hello"


def test_streams_chat_completion_events() -> None:
    transport = FakeTransport()
    transport.stream_lines = [
        b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n',
        b"\n",
        b'data: {"choices":[{"delta":{"content":"lo"}}]}\n',
        b"\n",
        b"data: [DONE]\n",
        b"\n",
    ]
    client = make_client(transport)

    events = list(
        client.chat.completions_stream(
            model="grok-4-1-fast-non-reasoning",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert events == [
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
    ]
    assert transport.stream_requests[0]["json_body"]["stream"] is True


def test_creates_gets_deletes_responses() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/responses",
        {
            "id": "resp_123",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "created"}],
                }
            ],
        },
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/responses/resp_123?include=messages",
        {"id": "resp_123", "output_text": "hello"},
    )
    transport.add_json_response(
        "DELETE",
        "https://api.x.ai/v1/responses/resp_123",
        {"id": "resp_123", "deleted": True},
    )
    client = make_client(transport)

    created = client.responses.create(model="grok-4-1-fast-non-reasoning", input="hi")
    fetched = client.responses.get("resp_123", include="messages")
    deleted = client.responses.delete("resp_123")

    assert created["id"] == "resp_123"
    assert client.responses.extract_text(created) == "created"
    assert fetched["output_text"] == "hello"
    assert deleted["deleted"] is True


def test_streams_response_events() -> None:
    transport = FakeTransport()
    transport.stream_lines = [
        b'data: {"type":"response.output_text.delta","delta":"x"}\n',
        b"\n",
        b"data: [DONE]\n",
        b"\n",
    ]
    client = make_client(transport)

    events = list(client.responses.stream(model="grok-4-1-fast-non-reasoning", input="hi"))

    assert events == [{"type": "response.output_text.delta", "delta": "x"}]


def test_drains_final_sse_event_without_trailing_blank_line() -> None:
    """Server may close connection after a data: line without a trailing
    blank-line separator. The parser must still yield that final event
    instead of silently dropping it."""
    transport = FakeTransport()
    transport.stream_lines = [
        b'data: {"type":"response.output_text.delta","delta":"first"}\n',
        b"\n",
        b'data: {"type":"response.completed","response":{"usage":{"input_tokens":1,"output_tokens":1}}}\n',
        # No trailing blank line before the server closes the stream.
    ]
    client = make_client(transport)

    events = list(client.responses.stream(model="grok-4-1-fast-non-reasoning", input="hi"))

    assert events == [
        {"type": "response.output_text.delta", "delta": "first"},
        {"type": "response.completed", "response": {"usage": {"input_tokens": 1, "output_tokens": 1}}},
    ]


def test_generates_and_edits_images() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/images/generations",
        {
            "data": [
                {
                    "url": "https://cdn.x.ai/generated.png",
                    "b64_json": "YWJj",
                }
            ]
        },
    )
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/images/edits",
        {
            "data": [
                {
                    "url": "https://cdn.x.ai/edited.png",
                }
            ]
        },
    )
    client = make_client(transport)

    generated = client.images.generate(
        model="grok-imagine-image",
        prompt="A clean line-art icon set.",
    )
    edited = client.images.edit(
        model="grok-imagine-image",
        prompt="Turn this into a pencil sketch.",
        image={
            "type": "image_url",
            "url": "https://example.com/source.png",
        },
    )

    assert client.images.extract_urls(generated) == ["https://cdn.x.ai/generated.png"]
    assert client.images.extract_base64_images(generated) == ["YWJj"]
    assert client.images.extract_urls(edited) == ["https://cdn.x.ai/edited.png"]


def test_generates_edits_and_polls_videos() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/videos/generations",
        {"request_id": "vidreq_123", "status": "queued"},
    )
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/videos/edits",
        {"request_id": "vidreq_456", "status": "queued"},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/videos/vidreq_123",
        {
            "request_id": "vidreq_123",
            "status": "done",
            "video": {"url": "https://cdn.x.ai/generated.mp4"},
        },
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/videos/vidreq_456",
        {
            "request_id": "vidreq_456",
            "status": "done",
            "video": {"url": "https://cdn.x.ai/edited.mp4"},
        },
    )
    client = make_client(transport)

    generated = client.videos.generate(
        model="grok-imagine-video",
        prompt="A camera orbit around a compass on a desk.",
    )
    edited = client.videos.edit(
        model="grok-imagine-video",
        prompt="Turn this into noir lighting.",
        video={"type": "video_url", "url": "https://example.com/source.mp4"},
    )
    done, generated_result = client.videos.poll_result("vidreq_123")
    edited_result = client.videos.get("vidreq_456")

    assert client.videos.extract_request_id(generated) == "vidreq_123"
    assert client.videos.extract_request_id(edited) == "vidreq_456"
    assert client.videos.extract_video_url(generated_result) == "https://cdn.x.ai/generated.mp4"
    assert client.videos.extract_video_url(edited_result) == "https://cdn.x.ai/edited.mp4"


def test_uploads_lists_gets_and_deletes_files() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/files",
        {"id": "file_123"},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/files?purpose=batch",
        {"data": [{"id": "file_123"}]},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/files/file_123",
        {"id": "file_123"},
    )
    transport.add_json_response(
        "DELETE",
        "https://api.x.ai/v1/files/file_123",
        {"id": "file_123", "deleted": True},
    )
    client = make_client(transport)

    uploaded = client.files.upload(
        file=b'{"custom_id":"1"}\n',
        filename="requests.jsonl",
        purpose="batch",
    )
    listed = client.files.list(purpose="batch")
    fetched = client.files.get("file_123")
    deleted = client.files.delete("file_123")

    assert uploaded["id"] == "file_123"
    assert listed["data"][0]["id"] == "file_123"
    assert fetched["id"] == "file_123"
    assert deleted["deleted"] is True
    body = transport.requests[0]["body"]
    assert b'filename="requests.jsonl"' in body


def test_batches_endpoints() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/batches",
        {"id": "batch_123"},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/batches?limit=10",
        {"data": [{"id": "batch_123"}]},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/batches/batch_123",
        {"id": "batch_123", "status": "running"},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/batches/batch_123/requests?limit=2",
        {"data": [{"id": "req_1"}]},
    )
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/batches/batch_123/requests",
        {"added": 1},
    )
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/batches/batch_123/results?limit=2",
        {"data": [{"id": "result_1"}]},
    )
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/batches/batch_123:cancel",
        {"id": "batch_123", "status": "cancelled"},
    )
    client = make_client(transport)

    created = client.batches.create(endpoint="/v1/responses", requests=[])
    listed = client.batches.list(limit=10)
    fetched = client.batches.get("batch_123")
    requests_result = client.batches.list_requests("batch_123", limit=2)
    added = client.batches.add_requests(
        "batch_123",
        requests=[
            {
                "batch_request_id": "req_1",
                "model": "grok-4-1-fast-non-reasoning",
                "messages": [{"role": "user", "content": "hello"}],
            }
        ],
    )
    results = client.batches.results("batch_123", limit=2)
    cancelled = client.batches.cancel("batch_123")

    assert created["id"] == "batch_123"
    assert listed["data"][0]["id"] == "batch_123"
    assert fetched["status"] == "running"
    assert requests_result["data"][0]["id"] == "req_1"
    assert added["added"] == 1
    assert results["data"][0]["id"] == "result_1"
    assert cancelled["status"] == "cancelled"
    assert transport.requests[4]["json_body"] == {
        "batch_requests": [
            {
                "batch_request_id": "req_1",
                "batch_request": {
                    "chat_get_completion": {
                        "model": "grok-4-1-fast-non-reasoning",
                        "messages": [{"role": "user", "content": "hello"}],
                    }
                },
            }
        ]
    }


def test_tokenize_text() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "POST",
        "https://api.x.ai/v1/tokenize-text",
        {
            "token_ids": [
                {"token_id": 1},
                {"token_id": 2},
                {"token_id": 3},
            ]
        },
    )
    client = make_client(transport)

    result = client.tokenize.text(
        text="Hello world",
        model="grok-4-1-fast-non-reasoning",
    )

    assert client.tokenize.extract_token_ids(result) == [1, 2, 3]
    assert client.tokenize.count_tokens(result) == 3


def test_voice_endpoints() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/tts/voices",
        {
            "voices": [
                {"voice_id": "alloy"},
                {"voice_id": "verse"},
            ]
        },
    )
    transport.add_bytes_response(
        "POST",
        "https://api.x.ai/v1/tts",
        b"RIFF....WAVE",
    )
    client = make_client(transport)

    voices = client.voice.list_voices()
    audio = client.voice.synthesize(
        voice="alloy",
        input="Hello world",
        language="en",
        format="wav",
    )

    assert client.voice.extract_voice_ids(voices) == ["alloy", "verse"]
    assert audio == b"RIFF....WAVE"
    assert transport.requests[1]["json_body"] == {
        "voice": "alloy",
        "text": "Hello world",
        "language": "en",
        "format": "wav",
    }


def test_deferred_completion_get() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/chat/deferred-completion/req_123",
        {"id": "req_123", "status": "completed"},
    )
    client = make_client(transport)

    result = client.chat.deferred_completion_get("req_123")

    assert result["status"] == "completed"


def test_raises_api_error_for_error_payload() -> None:
    transport = FakeTransport()
    transport.add_json_response(
        "GET",
        "https://api.x.ai/v1/models",
        {
            "error": {
                "message": "Bad request",
                "type": "invalid_request_error",
                "code": "bad_request",
            }
        },
        status_code=400,
    )
    client = make_client(transport)

    with pytest.raises(XAIAPIError) as exc:
        client.models.list()

    assert exc.value.status_code == 400
    assert exc.value.error_type == "invalid_request_error"


def test_raises_api_error_for_plain_text_body() -> None:
    transport = FakeTransport()
    transport.response_map[("GET", "https://api.x.ai/v1/models")] = TransportResponse(
        status_code=500,
        headers={"Content-Type": "text/plain"},
        body=b"server error",
    )
    client = make_client(transport)

    with pytest.raises(XAIAPIError) as exc:
        client.models.list()

    assert exc.value.status_code == 500
    assert "status 500" in str(exc.value)


def test_urllib_transport_builds_json_request() -> None:
    transport = UrllibTransport()
    request = transport._build_request(
        method="POST",
        url="https://api.x.ai/v1/responses",
        headers={"X-Test": "1"},
        params={"include": "messages"},
        json_body={"model": "grok-4-1-fast-non-reasoning"},
        body=None,
    )

    assert request.full_url == "https://api.x.ai/v1/responses?include=messages"
    assert request.get_method() == "POST"
    assert request.headers["Content-type"] == "application/json"


def test_encode_data_uri() -> None:
    result = encode_data_uri(b"abc", mime_type="image/png")

    assert result == "data:image/png;base64,YWJj"


# ── Chat tool call extraction ─────────────────────────────────────────────


def test_chat_extract_tool_calls() -> None:
    completion = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location": "SF"}',
                            },
                        }
                    ],
                }
            }
        ]
    }
    transport = FakeTransport()
    transport.add_json_response("POST", "https://api.x.ai/v1/chat/completions", completion)
    client = make_client(transport)
    result = client.chat.completions_create(model="grok-4", messages=[])

    tool_calls = client.chat.extract_tool_calls(result)

    assert len(tool_calls) == 1
    assert tool_calls[0]["id"] == "call_abc"
    assert tool_calls[0]["name"] == "get_weather"
    assert tool_calls[0]["arguments"] == {"location": "SF"}


def test_chat_extract_tool_calls_empty() -> None:
    completion = {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}
    transport = FakeTransport()
    client = make_client(transport)

    assert client.chat.extract_tool_calls(completion) == []


def test_chat_extract_usage() -> None:
    completion = {
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "reasoning_tokens": 20,
            "prompt_tokens_details": {"cached_tokens": 30},
        }
    }
    transport = FakeTransport()
    client = make_client(transport)

    usage = client.chat.extract_usage(completion)

    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50
    assert usage["reasoning_tokens"] == 20
    assert usage["cached_tokens"] == 30


def test_chat_make_tool_result_message() -> None:
    transport = FakeTransport()
    client = make_client(transport)

    msg = client.chat.make_tool_result_message("call_abc", '{"temp": 72}')

    assert msg == {"role": "tool", "tool_call_id": "call_abc", "content": '{"temp": 72}'}


# ── Responses tool call extraction ─────────────────────────────────────────


def test_responses_extract_tool_calls() -> None:
    response = {
        "id": "resp_123",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_xyz",
                "name": "get_temperature",
                "arguments": '{"location": "NYC"}',
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "checking..."}],
            },
        ],
    }
    transport = FakeTransport()
    client = make_client(transport)

    tool_calls = client.responses.extract_tool_calls(response)

    assert len(tool_calls) == 1
    assert tool_calls[0]["call_id"] == "call_xyz"
    assert tool_calls[0]["name"] == "get_temperature"
    assert tool_calls[0]["arguments"] == {"location": "NYC"}


def test_responses_extract_usage() -> None:
    response = {
        "usage": {
            "input_tokens": 200,
            "output_tokens": 80,
            "total_tokens": 280,
            "input_tokens_details": {"cached_tokens": 50},
            "output_tokens_details": {"reasoning_tokens": 40},
        }
    }
    transport = FakeTransport()
    client = make_client(transport)

    usage = client.responses.extract_usage(response)

    assert usage["input_tokens"] == 200
    assert usage["output_tokens"] == 80
    assert usage["total_tokens"] == 280
    assert usage["reasoning_tokens"] == 40
    assert usage["cached_tokens"] == 50


def test_responses_extract_usage_legacy_field_fallback() -> None:
    """If a response still emits ``cached_prompt_text_tokens`` at the top
    level (older endpoints), we fall back to that rather than zero."""
    response = {
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "reasoning_tokens": 2,
            "cached_prompt_text_tokens": 3,
        }
    }
    transport = FakeTransport()
    client = make_client(transport)

    usage = client.responses.extract_usage(response)

    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 5
    assert usage["reasoning_tokens"] == 2
    assert usage["cached_tokens"] == 3


def test_responses_extract_citations() -> None:
    response = {
        "citations": [
            {"url": "https://example.com", "snippet": "relevant info"},
        ]
    }
    transport = FakeTransport()
    client = make_client(transport)

    citations = client.responses.extract_citations(response)

    assert len(citations) == 1
    assert citations[0]["url"] == "https://example.com"


def test_responses_make_tool_result() -> None:
    from src.xai_client import ResponsesAPI

    result = ResponsesAPI.make_tool_result("call_xyz", '{"temp": 59}')

    assert result == {
        "type": "function_call_output",
        "call_id": "call_xyz",
        "output": '{"temp": 59}',
    }


# ── Tool builders ──────────────────────────────────────────────────────────


def test_function_tool() -> None:
    tool = function_tool(
        "get_weather",
        description="Get weather for a city",
        parameters={
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    )

    assert tool == {
        "type": "function",
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    }


def test_function_tool_minimal() -> None:
    tool = function_tool("ping")

    assert tool == {"type": "function", "name": "ping"}


def test_chat_function_tool() -> None:
    tool = chat_function_tool(
        "get_weather",
        description="Get weather",
        parameters={"type": "object", "properties": {}},
    )

    assert tool == {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def test_web_search_tool() -> None:
    tool = web_search_tool(allowed_domains=["example.com"], enable_image_understanding=True)

    assert tool == {
        "type": "web_search",
        "filters": {"allowed_domains": ["example.com"]},
        "enable_image_understanding": True,
    }


def test_web_search_tool_minimal() -> None:
    assert web_search_tool() == {"type": "web_search"}


def test_x_search_tool() -> None:
    tool = x_search_tool(
        allowed_x_handles=["elonmusk"],
        from_date="2026-01-01",
        to_date="2026-04-01",
    )

    assert tool["type"] == "x_search"
    assert tool["allowed_x_handles"] == ["elonmusk"]
    assert tool["from_date"] == "2026-01-01"


def test_code_interpreter_tool() -> None:
    assert code_interpreter_tool() == {"type": "code_interpreter"}


def test_file_search_tool() -> None:
    tool = file_search_tool(["vs_abc"], max_num_results=5)

    assert tool == {
        "type": "file_search",
        "vector_store_ids": ["vs_abc"],
        "max_num_results": 5,
    }


def test_mcp_tool() -> None:
    tool = mcp_tool(
        "https://mcp.example.com/mcp",
        "my-tools",
        allowed_tools=["search", "fetch"],
        authorization="Bearer tok_123",
    )

    assert tool == {
        "type": "mcp",
        "server_url": "https://mcp.example.com/mcp",
        "server_label": "my-tools",
        "allowed_tools": ["search", "fetch"],
        "authorization": "Bearer tok_123",
    }
