#!/usr/bin/env python3
"""Smoke test LLM intent parsing via the real DeepSeek service layer.

Set LLM_PROVIDER_API_KEY in your shell before running this script.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("LLM_PROVIDER", "deepseek")
os.environ.setdefault("LLM_PROVIDER_API_URL", "https://api.deepseek.com/v1/chat/completions")
os.environ.setdefault("LLM_PROVIDER_MODEL", "deepseek-v4-flash")

sys.path.insert(0, "/root/business-clone/backend")

from app.services.v2_llm import get_llm_service

print("=" * 60)
print("LLM Service Integration Test")
print("=" * 60)

print("\nInitializing LLM service...")
service = get_llm_service()
print(f"  Provider URL: {service.provider.api_url}")
print(f"  Provider model: {service.provider.model}")

test_queries = [
    "查一下螺丝刀还有多少个",
    "进50个黄色手枪钻",
    "出了5个电钻",
    "扳手多少钱",
]

print("\nTesting intent parsing:")
for query in test_queries:
    print(f"\n  Query: '{query}'")
    result = service.parse_intent(query)
    print(f"    Intent: {result.intent_type}")
    print(f"    Item: {result.item_name}")
    print(f"    Qty: {result.quantity}")
    print(f"    Confidence: {result.confidence}")

print("\n" + "=" * 60)
print("LLM Service integration test complete")
print("=" * 60)
