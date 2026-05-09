from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, BinaryIO, Iterator, Mapping, MutableMapping, Protocol


JsonDict = dict[str, Any]


class XAIError(Exception):
    """Base widget error."""


class XAIConfigurationError(XAIError):
    """Raised when client configuration is invalid."""


class XAIAPIError(XAIError):
    """Raised when the xAI API returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_type: str | None = None,
        code: str | None = None,
        param: str | None = None,
        body: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.code = code
        self.param = param
        self.body = body


@dataclass
class TransportResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
        timeout: float | None = None,
    ) -> TransportResponse:
        """Execute a request and return the raw response."""

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """Execute a streaming request and yield raw lines."""


class UrllibTransport:
    """Default transport using the Python standard library."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
        timeout: float | None = None,
    ) -> TransportResponse:
        request = self._build_request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json_body=json_body,
            body=body,
        )
        urlopen_kwargs: dict[str, Any] = {}
        if timeout is not None:
            urlopen_kwargs["timeout"] = timeout
        try:
            with urllib.request.urlopen(request, **urlopen_kwargs) as response:
                return TransportResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            return TransportResponse(
                status_code=exc.code,
                headers=dict(exc.headers.items()),
                body=exc.read(),
            )

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        request = self._build_request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json_body=json_body,
            body=body,
        )
        urlopen_kwargs: dict[str, Any] = {}
        if timeout is not None:
            urlopen_kwargs["timeout"] = timeout
        try:
            with urllib.request.urlopen(request, **urlopen_kwargs) as response:
                for line in response:
                    yield line
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            raise _build_api_error(exc.code, payload) from exc

    def _build_request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None,
        params: Mapping[str, Any] | None,
        json_body: Any | None,
        body: bytes | None,
    ) -> urllib.request.Request:
        request_headers: MutableMapping[str, str] = dict(headers or {})
        final_url = _append_query_params(url, params)
        data = body
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        return urllib.request.Request(
            final_url,
            data=data,
            headers=dict(request_headers),
            method=method.upper(),
        )


class APIResource:
    def __init__(self, client: "XAIClient") -> None:
        self._client = client


class ChatAPI(APIResource):
    def completions_create(self, **payload: Any) -> JsonDict:
        return self._client._request_json("POST", "/chat/completions", json_body=payload)

    def completions_stream(self, **payload: Any) -> Iterator[JsonDict]:
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        for event in self._client._stream_sse(
            "POST",
            "/chat/completions",
            json_body=stream_payload,
        ):
            yield event

    def deferred_completion_get(self, request_id: str) -> JsonDict:
        return self._client._request_json("GET", f"/chat/deferred-completion/{request_id}")

    def extract_text(self, completion: Mapping[str, Any]) -> str:
        choices = completion.get("choices", [])
        parts: list[str] = []
        for choice in choices:
            message = choice.get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
        return "".join(parts)

    def extract_tool_calls(self, completion: Mapping[str, Any]) -> list[JsonDict]:
        """Extract tool calls from a chat completion response.

        Returns a list of dicts with keys: id, name, arguments (parsed JSON).
        """
        results: list[JsonDict] = []
        for choice in completion.get("choices", []):
            for tc in choice.get("message", {}).get("tool_calls", []):
                func = tc.get("function", {})
                args_raw = func.get("arguments", "{}")
                try:
                    args = json.loads(args_raw)
                except (json.JSONDecodeError, TypeError):
                    args = args_raw
                results.append({
                    "id": tc.get("id"),
                    "name": func.get("name"),
                    "arguments": args,
                })
        return results

    def extract_usage(self, completion: Mapping[str, Any]) -> JsonDict:
        """Extract usage info from a chat completion response."""
        usage = completion.get("usage", {})
        details = usage.get("prompt_tokens_details", {})
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "reasoning_tokens": usage.get("reasoning_tokens", 0),
            "cached_tokens": details.get("cached_tokens", 0),
        }

    def make_tool_result_message(
        self, tool_call_id: str, content: str
    ) -> JsonDict:
        """Build a tool result message for multi-turn chat completions."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }


class ResponsesAPI(APIResource):
    def create(self, **payload: Any) -> JsonDict:
        return self._client._request_json("POST", "/responses", json_body=payload)

    def get(self, response_id: str, **params: Any) -> JsonDict:
        return self._client._request_json(
            "GET",
            f"/responses/{response_id}",
            params=params or None,
        )

    def delete(self, response_id: str) -> JsonDict:
        return self._client._request_json("DELETE", f"/responses/{response_id}")

    def stream(self, **payload: Any) -> Iterator[JsonDict]:
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        for event in self._client._stream_sse("POST", "/responses", json_body=stream_payload):
            yield event

    def extract_text(self, response: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and "text" in content:
                    parts.append(str(content["text"]))
        return "".join(parts)

    def extract_tool_calls(self, response: Mapping[str, Any]) -> list[JsonDict]:
        """Extract function_call items from a Responses API response.

        Returns a list of dicts with keys: call_id, name, arguments (parsed JSON).
        """
        results: list[JsonDict] = []
        for item in response.get("output", []):
            if item.get("type") != "function_call":
                continue
            args_raw = item.get("arguments", "{}")
            try:
                args = json.loads(args_raw)
            except (json.JSONDecodeError, TypeError):
                args = args_raw
            results.append({
                "call_id": item.get("call_id"),
                "name": item.get("name"),
                "arguments": args,
            })
        return results

    def extract_usage(self, response: Mapping[str, Any]) -> JsonDict:
        """Extract usage info from a Responses API response.

        xAI's Responses API returns ``input_tokens`` / ``output_tokens``
        at the top level (not the ``prompt_tokens`` / ``completion_tokens``
        names Chat Completions uses). ``cached_tokens`` lives under
        ``input_tokens_details`` and ``reasoning_tokens`` under
        ``output_tokens_details``. This helper flattens them into a
        single dict with canonical names.
        """
        usage = response.get("usage", {})
        input_details = usage.get("input_tokens_details") or {}
        output_details = usage.get("output_tokens_details") or {}
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "reasoning_tokens": (
                output_details.get("reasoning_tokens")
                or usage.get("reasoning_tokens", 0)
            ),
            "cached_tokens": (
                input_details.get("cached_tokens")
                or usage.get("cached_prompt_text_tokens", 0)
            ),
        }

    def extract_citations(self, response: Mapping[str, Any]) -> list[JsonDict]:
        """Extract citation sources from a Responses API response."""
        return list(response.get("citations", []))

    @staticmethod
    def make_tool_result(call_id: str, output: str) -> JsonDict:
        """Build a function_call_output input item for multi-turn responses."""
        return {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
        }


class ModelsAPI(APIResource):
    def list(self) -> JsonDict:
        return self._client._request_json("GET", "/models")

    def get(self, model_id: str) -> JsonDict:
        return self._client._request_json("GET", f"/models/{model_id}")

    def list_language_models(self) -> JsonDict:
        return self._client._request_json("GET", "/language-models")

    def get_language_model(self, model_id: str) -> JsonDict:
        return self._client._request_json("GET", f"/language-models/{model_id}")

    def list_image_generation_models(self) -> JsonDict:
        return self._client._request_json("GET", "/image-generation-models")

    def get_image_generation_model(self, model_id: str) -> JsonDict:
        return self._client._request_json("GET", f"/image-generation-models/{model_id}")


class ImagesAPI(APIResource):
    def generate(self, **payload: Any) -> JsonDict:
        return self._client._request_json("POST", "/images/generations", json_body=payload)

    def edit(self, **payload: Any) -> JsonDict:
        return self._client._request_json("POST", "/images/edits", json_body=payload)

    def extract_urls(self, response: Mapping[str, Any]) -> list[str]:
        urls: list[str] = []
        for item in response.get("data", []):
            url = item.get("url")
            if isinstance(url, str):
                urls.append(url)
        return urls

    def extract_base64_images(self, response: Mapping[str, Any]) -> list[str]:
        images: list[str] = []
        for item in response.get("data", []):
            base64_image = item.get("b64_json")
            if isinstance(base64_image, str):
                images.append(base64_image)
        return images


class VideosAPI(APIResource):
    def generate(self, **payload: Any) -> JsonDict:
        return self._client._request_json("POST", "/videos/generations", json_body=payload)

    def edit(self, **payload: Any) -> JsonDict:
        return self._client._request_json("POST", "/videos/edits", json_body=payload)

    def get(self, request_id: str) -> JsonDict:
        return self._client._request_json("GET", f"/videos/{request_id}")

    def extract_request_id(self, response: Mapping[str, Any]) -> str | None:
        request_id = response.get("request_id")
        if isinstance(request_id, str):
            return request_id
        return None

    def extract_video_url(self, response: Mapping[str, Any]) -> str | None:
        video = response.get("video", {})
        url = video.get("url")
        if isinstance(url, str):
            return url
        return None

    def poll_result(self, request_id: str) -> tuple[bool, JsonDict]:
        """Check if an async request has finished.

        Returns (is_done, response). The caller controls polling frequency:

            while True:
                done, result = videos.poll_result(req_id)
                if done:
                    break
                time.sleep(2)
        """
        response = self.get(request_id)
        status = response.get("status")
        done = status in {"done", "completed", "failed", "expired"}
        return done, response


class FilesAPI(APIResource):
    def upload(
        self,
        *,
        file: bytes | BinaryIO,
        filename: str,
        purpose: str | None = None,
        content_type: str | None = None,
        extra_fields: Mapping[str, Any] | None = None,
    ) -> JsonDict:
        fields: list[tuple[str, str]] = []
        if purpose is not None:
            fields.append(("purpose", purpose))
        for key, value in (extra_fields or {}).items():
            fields.append((key, str(value)))
        file_bytes = _coerce_bytes(file)
        multipart_body, boundary = _encode_multipart(
            fields=fields,
            files=[
                (
                    "file",
                    filename,
                    file_bytes,
                    content_type or _guess_content_type(filename),
                )
            ],
        )
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self._client._request_json("POST", "/files", headers=headers, body=multipart_body)

    def list(self, **params: Any) -> JsonDict:
        return self._client._request_json("GET", "/files", params=params or None)

    def get(self, file_id: str) -> JsonDict:
        return self._client._request_json("GET", f"/files/{file_id}")

    def delete(self, file_id: str) -> JsonDict:
        return self._client._request_json("DELETE", f"/files/{file_id}")


class BatchesAPI(APIResource):
    def create(self, **payload: Any) -> JsonDict:
        return self._client._request_json("POST", "/batches", json_body=payload)

    def list(self, **params: Any) -> JsonDict:
        return self._client._request_json("GET", "/batches", params=params or None)

    def get(self, batch_id: str) -> JsonDict:
        return self._client._request_json("GET", f"/batches/{batch_id}")

    def list_requests(self, batch_id: str, **params: Any) -> JsonDict:
        return self._client._request_json(
            "GET",
            f"/batches/{batch_id}/requests",
            params=params or None,
        )

    def add_requests(self, batch_id: str, *, requests: list[JsonDict]) -> JsonDict:
        normalized_requests: list[JsonDict] = []
        for request in requests:
            if "batch_request" in request:
                normalized_requests.append(dict(request))
                continue
            batch_request_id = request.get("batch_request_id")
            raw_request = {key: value for key, value in request.items() if key != "batch_request_id"}
            if any(key in raw_request for key in ("messages", "audio", "modalities")):
                batch_request: JsonDict = {"chat_get_completion": raw_request}
            elif "input" in raw_request:
                batch_request = {"responses": raw_request}
            elif "image" in raw_request and "prompt" in raw_request:
                batch_request = {"image_edit": raw_request}
            elif "prompt" in raw_request:
                batch_request = {"image_generation": raw_request}
            else:
                batch_request = raw_request
            item: JsonDict = {"batch_request": batch_request}
            if batch_request_id is not None:
                item["batch_request_id"] = batch_request_id
            normalized_requests.append(item)
        response = self._client._request(
            "POST",
            f"/batches/{batch_id}/requests",
            json_body={"batch_requests": normalized_requests},
        )
        if response.body.strip() in (b"", b"null"):
            return {"ok": True}
        return _decode_json(response.body)

    def results(self, batch_id: str, **params: Any) -> JsonDict:
        return self._client._request_json(
            "GET",
            f"/batches/{batch_id}/results",
            params=params or None,
        )

    def cancel(self, batch_id: str) -> JsonDict:
        return self._client._request_json("POST", f"/batches/{batch_id}:cancel")


class TokenizeAPI(APIResource):
    def text(self, *, text: str, model: str | None = None) -> JsonDict:
        payload: JsonDict = {"text": text}
        if model is not None:
            payload["model"] = model
        return self._client._request_json("POST", "/tokenize-text", json_body=payload)

    def extract_token_ids(self, response: Mapping[str, Any]) -> list[int]:
        token_ids: list[int] = []
        for item in response.get("token_ids", []):
            token_id = item.get("token_id")
            if isinstance(token_id, int):
                token_ids.append(token_id)
        return token_ids

    def count_tokens(self, response: Mapping[str, Any]) -> int:
        return len(self.extract_token_ids(response))


class VoiceAPI(APIResource):
    def synthesize(self, **payload: Any) -> bytes:
        request_payload = dict(payload)
        if "text" not in request_payload and "input" in request_payload:
            request_payload["text"] = request_payload.pop("input")
        return self._client._request_bytes("POST", "/tts", json_body=request_payload)

    def list_voices(self) -> JsonDict:
        return self._client._request_json("GET", "/tts/voices")

    def extract_voice_ids(self, response: Mapping[str, Any]) -> list[str]:
        voice_ids: list[str] = []
        for item in response.get("voices", []):
            voice_id = item.get("voice_id")
            if isinstance(voice_id, str):
                voice_ids.append(voice_id)
        return voice_ids


class XAIClient:
    """Stdlib-only xAI backend client for glue code usage."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.x.ai/v1",
        timeout: float | None = 600.0,
        transport: Transport | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("XAI_API_KEY")
        if not resolved_api_key:
            raise XAIConfigurationError(
                "xAI API key is required. Pass api_key or set XAI_API_KEY."
            )
        if not base_url:
            raise XAIConfigurationError("base_url must not be empty.")
        self.api_key = resolved_api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport or UrllibTransport()

        self.chat = ChatAPI(self)
        self.responses = ResponsesAPI(self)
        self.models = ModelsAPI(self)
        self.images = ImagesAPI(self)
        self.videos = VideosAPI(self)
        self.files = FilesAPI(self)
        self.batches = BatchesAPI(self)
        self.tokenize = TokenizeAPI(self)
        self.voice = VoiceAPI(self)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
    ) -> JsonDict:
        response = self._request(
            method,
            path,
            headers=headers,
            params=params,
            json_body=json_body,
            body=body,
        )
        return _decode_json(response.body)

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
    ) -> bytes:
        response = self._request(
            method,
            path,
            headers=headers,
            params=params,
            json_body=json_body,
            body=body,
        )
        return response.body

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
    ) -> TransportResponse:
        response = self._transport.request(
            method,
            self._build_url(path),
            headers=self._build_headers(headers),
            params=params,
            json_body=json_body,
            body=body,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise _build_api_error(response.status_code, response.body)
        return response

    def _stream_sse(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        body: bytes | None = None,
    ) -> Iterator[JsonDict]:
        stream_headers = {"Accept": "text/event-stream"}
        if headers:
            stream_headers.update(headers)
        event_data: list[str] = []
        for raw_line in self._transport.stream(
            method,
            self._build_url(path),
            headers=self._build_headers(stream_headers),
            params=params,
            json_body=json_body,
            body=body,
            timeout=self.timeout,
        ):
            line = raw_line.decode("utf-8").strip()
            if not line:
                if event_data:
                    payload = "".join(event_data)
                    event_data = []
                    if payload == "[DONE]":
                        return
                    yield _decode_json(payload.encode("utf-8"))
                continue
            if line.startswith("data:"):
                event_data.append(line[5:].strip())
        # Final drain: if the server closed the connection without a
        # trailing blank line, the last buffered event would otherwise be
        # lost. With long streams (big prompts → big replies) this shows
        # up as the tail of the final output_text.delta — or even the
        # response.completed frame — silently dropped.
        if event_data:
            payload = "".join(event_data)
            if payload and payload != "[DONE]":
                yield _decode_json(payload.encode("utf-8"))

    def _build_url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _build_headers(self, extra_headers: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "cartograph-xai-client-python/1.0.0",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers


def _append_query_params(url: str, params: Mapping[str, Any] | None) -> str:
    if not params:
        return url
    query_items: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                query_items.append((key, str(item)))
        else:
            query_items.append((key, str(value)))
    if not query_items:
        return url
    query = urllib.parse.urlencode(query_items)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query}"


def _decode_json(body: bytes) -> JsonDict:
    return json.loads(body.decode("utf-8"))


def _build_api_error(status_code: int, body: bytes) -> XAIAPIError:
    try:
        payload = _decode_json(body)
    except Exception:
        return XAIAPIError(
            f"xAI API request failed with status {status_code}.",
            status_code=status_code,
            body=body.decode("utf-8", errors="replace"),
        )
    error = payload.get("error", payload)
    if isinstance(error, str):
        error = {"message": error}
    elif not isinstance(error, dict):
        error = {"message": f"xAI API request failed with status {status_code}."}
    return XAIAPIError(
        error.get("message", f"xAI API request failed with status {status_code}."),
        status_code=status_code,
        error_type=error.get("type"),
        code=error.get("code"),
        param=error.get("param"),
        body=payload,
    )


def _coerce_bytes(file_or_bytes: bytes | BinaryIO) -> bytes:
    if isinstance(file_or_bytes, bytes):
        return file_or_bytes
    return file_or_bytes.read()


def _encode_multipart(
    *,
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"cartograph-{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields:
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"),
                b"",
                value.encode("utf-8"),
            ]
        )
    for field_name, filename, content, content_type in files:
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; '
                    f'filename="{filename}"'
                ).encode("utf-8"),
                f"Content-Type: {content_type}".encode("utf-8"),
                b"",
                content,
            ]
        )
    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    return b"\r\n".join(lines), boundary


def _guess_content_type(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


# ── Tool builders ──────────────────────────────────────────────────────────
# Convenience functions that produce tool definition dicts matching the xAI
# Responses API format.  Pass them in the ``tools`` list of a request payload.


def function_tool(
    name: str,
    *,
    description: str = "",
    parameters: JsonDict | None = None,
) -> JsonDict:
    """Build a custom function tool definition."""
    tool: JsonDict = {"type": "function", "name": name}
    if description:
        tool["description"] = description
    if parameters is not None:
        tool["parameters"] = parameters
    return tool


def web_search_tool(
    *,
    allowed_domains: list[str] | None = None,
    excluded_domains: list[str] | None = None,
    enable_image_understanding: bool = False,
    user_location_country: str | None = None,
    user_location_city: str | None = None,
    user_location_timezone: str | None = None,
) -> JsonDict:
    """Build a web_search built-in tool definition."""
    tool: JsonDict = {"type": "web_search"}
    filters: JsonDict = {}
    if allowed_domains:
        filters["allowed_domains"] = allowed_domains
    if excluded_domains:
        filters["excluded_domains"] = excluded_domains
    if filters:
        tool["filters"] = filters
    if enable_image_understanding:
        tool["enable_image_understanding"] = True
    if user_location_country:
        tool["user_location_country"] = user_location_country
    if user_location_city:
        tool["user_location_city"] = user_location_city
    if user_location_timezone:
        tool["user_location_timezone"] = user_location_timezone
    return tool


def x_search_tool(
    *,
    allowed_x_handles: list[str] | None = None,
    excluded_x_handles: list[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    enable_image_understanding: bool = False,
    enable_video_understanding: bool = False,
) -> JsonDict:
    """Build an x_search built-in tool definition."""
    tool: JsonDict = {"type": "x_search"}
    if allowed_x_handles:
        tool["allowed_x_handles"] = allowed_x_handles
    if excluded_x_handles:
        tool["excluded_x_handles"] = excluded_x_handles
    if from_date:
        tool["from_date"] = from_date
    if to_date:
        tool["to_date"] = to_date
    if enable_image_understanding:
        tool["enable_image_understanding"] = True
    if enable_video_understanding:
        tool["enable_video_understanding"] = True
    return tool


def code_interpreter_tool() -> JsonDict:
    """Build a code_interpreter built-in tool definition."""
    return {"type": "code_interpreter"}


def file_search_tool(
    vector_store_ids: list[str],
    *,
    max_num_results: int | None = None,
) -> JsonDict:
    """Build a file_search (collections search) built-in tool definition."""
    tool: JsonDict = {"type": "file_search", "vector_store_ids": vector_store_ids}
    if max_num_results is not None:
        tool["max_num_results"] = max_num_results
    return tool


def mcp_tool(
    server_url: str,
    server_label: str,
    *,
    server_description: str | None = None,
    allowed_tools: list[str] | None = None,
    authorization: str | None = None,
    headers: JsonDict | None = None,
) -> JsonDict:
    """Build a remote MCP tool definition."""
    tool: JsonDict = {
        "type": "mcp",
        "server_url": server_url,
        "server_label": server_label,
    }
    if server_description:
        tool["server_description"] = server_description
    if allowed_tools:
        tool["allowed_tools"] = allowed_tools
    if authorization:
        tool["authorization"] = authorization
    if headers:
        tool["headers"] = headers
    return tool


# ── Chat Completions tool format ───────────────────────────────────────────
# Chat Completions uses a slightly different tool shape than Responses API.


def chat_function_tool(
    name: str,
    *,
    description: str = "",
    parameters: JsonDict | None = None,
) -> JsonDict:
    """Build a function tool definition for the Chat Completions API."""
    func: JsonDict = {"name": name}
    if description:
        func["description"] = description
    if parameters is not None:
        func["parameters"] = parameters
    return {"type": "function", "function": func}


def encode_data_uri(
    data: bytes | BinaryIO,
    *,
    mime_type: str | None = None,
    filename: str | None = None,
) -> str:
    import base64

    raw = _coerce_bytes(data)
    resolved_mime_type = mime_type
    if resolved_mime_type is None and filename is not None:
        resolved_mime_type = _guess_content_type(filename)
    if resolved_mime_type is None:
        resolved_mime_type = "application/octet-stream"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{resolved_mime_type};base64,{encoded}"
