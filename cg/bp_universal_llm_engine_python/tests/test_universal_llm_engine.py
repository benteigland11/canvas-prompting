"""Tests for the universal-llm-engine blueprint API surface."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.universal_llm_engine import hello


def test_hello():
    assert hello() == "universal-llm-engine"
