"""Example usage of the universal-llm-engine blueprint."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.universal_llm_engine import hello


if __name__ == "__main__":
    print(hello())
