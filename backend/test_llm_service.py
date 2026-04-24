#!/usr/bin/env python3
"""Test LLM intent parsing via the service layer."""

import sys
import os

# Set environment variables before importing
os.environ["LLM_API_URL"] = "https://gptrr.qzz.io/v1/chat/completions"
os.environ["LLM_API_KEY"] = "sk-c4f3546c266c51bacfb1e329ae3bf344192ee677f262c32bbab192e4f02c5e5c"
os.environ["LLM_MODEL"] = "kimi-k2.6"

sys.path.insert(0, "/tmp/Business/backend")

from app.services.v2_llm import get_llm_service, parse_stock_query_intent

print("=" * 60)
print("LLM Service Integration Test")
print("=" * 60)

# Initialize service
print("\nInitializing LLM service...")
service = get_llm_service()
print(f"  Mock mode: {service._use_mock}")
if not service._use_mock:
    print(f"  Provider URL: {service._provider.api_url}")
    print(f"  Provider model: {service._provider.model}")

# Test cases
test_queries = [
    "查一下螺丝刀还有多少个",
    "进50个黄色手枪钻",
    "出了5个电钻",
    "扳手多少钱",
]

print("\n Testing intent parsing:")
for query in test_queries:
    print(f"\n  Query: '{query}'")
    result = service.parse_intent(query)
    print(f"    Intent: {result.intent_type}")
    print(f"    Item: {result.item_name}")
    print(f"    Qty: {result.quantity}")
    print(f"    Confidence: {result.confidence}")

print("\n" + "=" * 60)
print("✅ LLM Service integration test complete!")
print("=" * 60)
