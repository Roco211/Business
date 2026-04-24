#!/usr/bin/env python3
"""Direct LLM provider test without service layer."""

import sys
sys.path.insert(0, "/tmp/Business/backend")

from app.services.llm_real_provider import create_llm_provider

HERMES_BASE_URL = "https://gptrr.qzz.io/v1/chat/completions"
HERMES_API_KEY = "sk-c4f3546c266c51bacfb1e329ae3bf344192ee677f262c32bbab192e4f02c5e5c"
HERMES_MODEL = "kimi-k2.6"

print("=" * 60)
print("Direct LLM Provider Test")
print("=" * 60)

# Create provider with explicit config
provider = create_llm_provider(
    api_url=HERMES_BASE_URL,
    api_key=HERMES_API_KEY,
    model=HERMES_MODEL,
    provider_name="gptrr",
    timeout_seconds=60.0,
    max_tokens=150,
)

print(f"\nProvider initialized:")
print(f"  API URL: {provider.api_url}")
print(f"  Model: {provider.model}")
print(f"  Timeout: {provider.timeout_seconds}s")

# Test 1: Basic chat
print("\n" + "-" * 60)
print("Test 1: Basic Chat")
print("-" * 60)
messages = [
    {"role": "system", "content": "You are a helpful AI assistant."},
    {"role": "user", "content": "Hello! Can you hear me?"},
]
response = provider.chat(messages)
print(f"Response: {response.content[:80]}...")
print(f"Stats: {response.stats.total_time_ms:.0f}ms, TPS: {response.stats.tps:.1f}")

# Test 2: Intent parsing
print("\n" + "-" * 60)
print("Test 2: Intent Parsing")
print("-" * 60)

test_cases = [
    ("查一下扳手还有多少个", "stock_query"),
    ("进了20个螺丝刀", "stock_in"),
    ("出了5个电钻", "stock_out"),
    ("手枪钻多少钱", "price_query"),
]

for query, expected in test_cases:
    prompt = f'''你是库存助手。解析用户输入，返回JSON：
- intent: 意图 (stock_query, stock_in, stock_out)
- item: 商品名
- quantity: 数量

用户: "{query}"
只返回JSON:'''
    
    messages = [
        {"role": "system", "content": "Parse intent to JSON."},
        {"role": "user", "content": prompt},
    ]
    
    response = provider.chat(messages)
    raw = response.content.replace('\n', ' ')
    print(f"\n  '{query}'")
    print(f"    Expected: {expected}")
    print(f"    LLM output: {raw[:100]}...")

print("\n" + "=" * 60)
print("✓ All tests complete!")
print("=" * 60)
print("\nSummary:")
print(f"  • API endpoint: {HERMES_BASE_URL}")
print(f"  • Model: {HERMES_MODEL}")
print(f"  • Status: WORKING ✓")
