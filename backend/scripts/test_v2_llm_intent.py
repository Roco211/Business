#!/usr/bin/env python3
"""测试 V2 LLM 意图识别服务"""
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

from app.services.v2_llm import LLMService, get_llm_service


def test_rule_based_intent():
    """测试基于规则的意图识别（无需 LLM API）"""
    print("=" * 60)
    print("V2 LLM Intent Recognition Test")
    print("=" * 60)
    
    # Use mock mode (no API key needed)
    service = LLMService(provider=None)
    
    test_cases = [
        ("螺丝刀还有几个？", "stock_query", "螺丝刀"),
        ("进货了10把锤子", "stock_in", "锤子"),
        ("今天卖了5个扳手", "stock_out", "扳手"),
        ("查一下库存", "stock_query", None),
        ("入库采购了20件钻头", "stock_in", "钻头"),
        ("出库发货3箱油漆", "stock_out", "油漆"),
        ("hello world", "unknown", None),
    ]
    
    print("\n[Rule-Based Intent Parsing]")
    passed = 0
    for text, expected_intent, expected_item in test_cases:
        result = service.parse_intent(text)
        status = "✓" if result.intent_type == expected_intent else "✗"
        if result.intent_type == expected_intent:
            passed += 1
        print(f"  {status} \"{text}\"")
        print(f"    Intent: {result.intent_type} (expected: {expected_intent})")
        print(f"    Item: {result.item_name}")
        print(f"    Qty: {result.quantity}")
        print(f"    Confidence: {result.confidence}")
        print()
    
    print(f"Rule-based: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_response_generation():
    """测试响应生成"""
    print("\n[Response Generation]")
    service = LLMService(provider=None)
    
    query_results = [
        {"item_name": "螺丝刀", "quantity": 15, "unit": "个"},
        {"item_name": "锤子", "quantity": 3, "unit": "把"},
    ]
    
    for qr in query_results:
        response = service.generate_response(qr, f"{qr['item_name']}还有吗？")
        print(f"  Query: {qr['item_name']}")
        print(f"  Response: {response.content}")
        print(f"  Confidence: {response.confidence}")
        print()
    
    return True


def test_service_singleton():
    """测试全局单例"""
    print("\n[Service Singleton]")
    try:
        svc1 = get_llm_service()
        svc2 = get_llm_service()
        print(f"  svc1 is svc2: {svc1 is svc2}")
        print(f"  Provider: {svc1.provider.provider_name if svc1.provider else 'not configured'}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    results = []
    
    results.append(("Rule-Based Intent", test_rule_based_intent()))
    results.append(("Response Generation", test_response_generation()))
    results.append(("Service Singleton", test_service_singleton()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for name, ok in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  [{status}] {name}")
    
    passed = sum(1 for _, ok in results if ok)
    print(f"\nTotal: {passed}/{len(results)} passed")
    
    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
