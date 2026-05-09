import pytest
from src.engine import ExecutionEngine
from src.grok_adapter import GrokAdapter

import os
from unittest.mock import patch

def test_engine_returns_grok_adapter():
    engine = ExecutionEngine()
    with patch.dict(os.environ, {"XAI_API_KEY": "dummy"}):
        client = engine.get_client("grok")
    assert isinstance(client, GrokAdapter)
    
def test_engine_returns_xai_adapter():
    engine = ExecutionEngine()
    with patch.dict(os.environ, {"XAI_API_KEY": "dummy"}):
        client = engine.get_client("xai")
    assert isinstance(client, GrokAdapter)

def test_engine_raises_on_unknown_provider():
    engine = ExecutionEngine()
    with pytest.raises(ValueError, match="Unsupported provider: unknown"):
        engine.get_client("unknown")
