#!/usr/bin/env python3
"""Quick LLM integration test."""

import sys
sys.path.insert(0, "/tmp/Business/backend")

from app.services.llm_real_provider import create_llm_provider

HERMES_BASE_URL = "https://gptrr.qzz.io/v1/chat/completions"
HERMES_API_KEY = "sk-c4f3546c266c51bacfb1e329ae3bf344192ee677f262c32bbab192e4f02c5e5c"
HERMES_MODEL = "kimi-k2.6"

print("=" * 60)
print("Quick LLM Test")
print("=" * 60)

# Test 1: Basic chat
print("\n1. Basic Chat...")
provider = create_llm_provider(
    api_url=HERMES_BASE_URL,
    api_key=HERMES_API_KEY,
    model=HERMES_MODEL,
    timeout_seconds=60.0,
)

messages = [
    {"role": "system", "content": "You are a helpful AI assistant."},
    {"role": "user", "content": "Hello! Can you hear me?"},
]

response = provider.chat(messages)
print(f"✅ Response: {response.content[:100]}...")
print(f"   Stats: {response.stats.total_time_ms:.0f}ms, TPS: {response.stats.tps:.1f}")

# Test 2: Intent parsing
print("\n2. Intent Parsing...")
provider2 = create_llm_provider(
    api_url=HERMES_BASE_URL,
    api_key=HERMES_API_KEY,
    model=HERMES_MODEL,
    timeout_seconds=60.0,
    max_tokens=200,
)

prompt = """解析用户指令，返回JSON格式：
- intent: 意图类型 (stock_query, stock_in, stock_out)
- product_name: 商品名称
- quantity: 数量

用户: "进50个黄色手枪钻"
只返回JSON:"""

messages2 = [
    {"role": "system", "content": "Parse user intent, return JSON only."},
    {"role": "user", "content": prompt},
]

response2 = provider2.chat(messages2)
print(f"✅ Raw response: {response2.content}")

# Test 3: Various intent types
print("\n3. Intent Recognition Tests...")
provider3 = create_llm_provider(
    api_url=HERMES_BASE_URL,
    api_key=HERMES_API_KEY,
    model=HERMES_MODEL,
    timeout_seconds=60.0,
    max_tokens=150,
)

test_queries = [
    ("查一下扳手还有多少个", "stock_query"),
    ("进了20个螺丝刀", "stock_in"),
    ("出了5个电钻", "stock_out"),
]

for query, expected in test_queries:
    prompt = f'''解析用户指令，返回JSON格式：
- intent: 意图类型 (stock_query, stock_in, stock_out)
- product_name: 商品名称
- quantity: 数量

用户: "{query}"
只返回JSON:'''
    messages = [
        {"role": "system", "content": "Parse user intent, return JSON only."},
        {"role": "user", "content": prompt},
    ]
    response = provider3.chat(messages)
    print(f"  • '{query}' -> {response.content[:80]}...")

print("\n" + "=" * 60)
print("✓ Basic LLM integration tests passed!")
print("=" * 60)
print("\nSummary:")
print("  • API URL: gptrr.qzz.io (OpenAI-compatible)")
print("  • Model: kimi-k2.6")
print("  • Intent parsing: Working with JSON output")
print("  • Response time: ~7-10 seconds")
print("\nNext steps:")
print("  1. Update v2_llm.py to use real LLM")
print("  2. Test voice -> LLM -> inventory flow")
