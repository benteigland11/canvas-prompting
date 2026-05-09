import asyncio
import json
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator, Any

from cg.cg_backend_llm_provider_interface_python.src.llm_provider_interface import (
    LLMClient, ChatRequest, ChatResponse, StreamEvent, Usage, StopReason,
    ToolCall, Message, FunctionTool, ServerTool, StreamStart, ContentDelta,
    ReasoningDelta, FunctionToolCall, ServerToolAnnounce, ServerToolResult,
    UsageEvent, StreamEnd, StreamError
)
from cg.cg_backend_xai_client_python.src.xai_client import XAIClient

class GrokAdapter(LLMClient):
    """Execution engine adapter mapping Grok to the canonical LLMClient protocol."""

    def __init__(self, api_key: str | None = None):
        self.client = XAIClient(api_key=api_key)
        self.max_context = 128000

    def supports(self, capability: str) -> bool:
        return capability in {
            "function_tools",
            "streaming"
        }

    def _build_payload(self, request: ChatRequest) -> dict[str, Any]:
        messages = []
        for msg in request.messages:
            m = {"role": msg.role, "content": msg.content}
            if msg.name:
                m["name"] = msg.name
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            messages.append(m)
        
        payload = {
            "model": request.model,
            "messages": messages,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        
        if request.tools:
            tools = []
            for t in request.tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters
                    }
                })
            payload["tools"] = tools
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
            
        return payload

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload = self._build_payload(request)
        loop = asyncio.get_running_loop()
        
        # Run synchronous xAI call in a background thread
        raw_response = await loop.run_in_executor(None, lambda: self.client.chat.completions_create(**payload))
        
        content = self.client.chat.extract_text(raw_response)
        usage_dict = self.client.chat.extract_usage(raw_response)
        usage = Usage(
            input_tokens=usage_dict.get("prompt_tokens", 0),
            output_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0),
            reasoning_tokens=usage_dict.get("reasoning_tokens", 0),
            cached_tokens=usage_dict.get("cached_tokens", 0)
        )
        
        raw_tool_calls = self.client.chat.extract_tool_calls(raw_response)
        tool_calls = []
        for tc in raw_tool_calls:
            args_str = json.dumps(tc["arguments"]) if not isinstance(tc["arguments"], str) else tc["arguments"]
            tool_calls.append(ToolCall(
                call_id=tc["id"],
                name=tc["name"],
                arguments=args_str
            ))
            
        stop_reason = raw_response.get("choices", [{}])[0].get("finish_reason", "stop")
        
        return ChatResponse(
            content=content,
            usage=usage,
            stop_reason=stop_reason, # type: ignore
            model=raw_response.get("model", request.model),
            tool_calls=tool_calls if tool_calls else None
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        payload = self._build_payload(request)
        loop = asyncio.get_running_loop()
        
        # Threaded generator pattern to convert sync HTTP stream to AsyncIterator
        q = queue.Queue()
        sentinel = object()
        
        def run_stream():
            try:
                for event in self.client.chat.completions_stream(**payload):
                    q.put(event)
            except Exception as e:
                q.put(e)
            finally:
                q.put(sentinel)
                
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(run_stream)
            yield StreamStart(model=request.model, stream_id="")
            
            while True:
                item = await loop.run_in_executor(pool, q.get)
                if item is sentinel:
                    break
                if isinstance(item, Exception):
                    yield StreamError(message=str(item), recoverable=False)
                    break
                    
                # Parse raw xAI stream chunks into canonical StreamEvents
                choices = item.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        yield ContentDelta(text=delta["content"])
                    
                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            if "function" in tc:
                                yield FunctionToolCall(
                                    call_id=tc.get("id", ""),
                                    name=tc["function"].get("name", ""),
                                    arguments=tc["function"].get("arguments", "")
                                )
                                
                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason:
                        yield StreamEnd(stop_reason=finish_reason)
                        
                if "usage" in item and item["usage"]:
                    u = item["usage"]
                    yield UsageEvent(
                        usage=Usage(
                            input_tokens=u.get("prompt_tokens", 0),
                            output_tokens=u.get("completion_tokens", 0),
                            total_tokens=u.get("total_tokens", 0)
                        ),
                        partial=False
                    )
