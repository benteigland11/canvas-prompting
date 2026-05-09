from typing import Dict, Type
from cg.cg_backend_llm_provider_interface_python.src.llm_provider_interface import LLMClient
from .grok_adapter import GrokAdapter

class ExecutionEngine:
    """Factory for instantiating vendor-specific LLM adapters that conform to the LLMClient protocol."""
    
    def __init__(self):
        self._adapters: Dict[str, Type[LLMClient]] = {
            "grok": GrokAdapter,
            "xai": GrokAdapter,
        }
        
    def get_client(self, provider: str, api_key: str | None = None) -> LLMClient:
        provider = provider.lower()
        if provider not in self._adapters:
            raise ValueError(f"Unsupported provider: {provider}. Supported providers: {list(self._adapters.keys())}")
        return self._adapters[provider](api_key=api_key)
