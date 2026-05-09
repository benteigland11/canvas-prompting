from typing import List

from cg.universal_llm_context_bundle_python.src.llm_context_bundle import (
    LLMContextBundle, LLMContextMessage, LLMContextTextPart, LLMContextImagePart
)
from cg.cg_backend_llm_provider_interface_python.src.llm_provider_interface import (
    ChatRequest, Message, FunctionTool, TextPart, ImagePart, ContentPart
)

def translate_bundle_to_request(bundle: LLMContextBundle, model: str, **kwargs) -> ChatRequest:
    """
    Translates the compiled spatial LLMContextBundle (Application layer) 
    into a provider-agnostic ChatRequest (Execution layer).
    """
    messages: List[Message] = []
    
    # 1. System Prompt -> System Message
    if bundle.system_prompt:
        messages.append(Message(role="system", content=bundle.system_prompt))
        
    # 2. Conversation Graph -> Messages
    for msg in bundle.messages:
        content = msg.content
        # Handle Multimodal Content Parts
        if isinstance(content, tuple) or isinstance(content, list):
            new_content: List[ContentPart] = []
            for part in content:
                if isinstance(part, LLMContextTextPart):
                    new_content.append(TextPart(text=part.text))
                elif isinstance(part, LLMContextImagePart):
                    # Keep image_url dict shape intact
                    image_url = part.image_url if isinstance(part.image_url, dict) else {"url": part.image_url}
                    new_content.append(ImagePart(image_url=image_url))
            content = new_content
            
        messages.append(Message(
            role=msg.role, # type: ignore
            content=content,
            name=msg.name,
            tool_call_id=msg.tool_call_id
            # Note: If the assistant made prior tool calls, the current llm_provider_interface Message 
            # lacks a `tool_calls` history array. That might need an upgrade in the interface widget later!
        ))
        
    # 3. Available Agency -> Function Tools
    tools = []
    for t in bundle.function_tools:
        tools.append(FunctionTool(
            name=t.tool_id,
            description=t.description,
            parameters=t.parameters
        ))
        
    return ChatRequest(
        model=model,
        messages=messages,
        tools=tools if tools else None,
        **kwargs
    )
