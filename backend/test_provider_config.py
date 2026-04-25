#!/usr/bin/env python3
"""Test LLM provider configuration and factory."""

import os
import sys

sys.path.insert(0, "/root/business-clone/backend")

from app.services.llm_real_provider import create_llm_provider, _ensure_chat_completions_url


def test_url_fix():
    """Test URL auto-fixing."""
    print("=" * 60)
    print("Test 1: URL Auto-fixing")
    print("=" * 60)

    test_cases = [
        ("https://ark.cn-beijing.volces.com/api/v3", "https://ark.cn-beijing.volces.com/api/v3/chat/completions"),
        ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1/chat/completions"),
        ("https://example.com/api/v1/chat/completions", "https://example.com/api/v1/chat/completions"),
        ("", ""),
    ]

    for input_url, expected in test_cases:
        result = _ensure_chat_completions_url(input_url)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] Input: '{input_url}'")
        print(f"         Output: '{result}'")
        if result != expected:
            print(f"         Expected: '{expected}'")

    print()


def test_provider_factory_openrouter():
    """Test factory with OpenRouter config."""
    print("=" * 60)
    print("Test 2: Provider Factory - OpenRouter")
    print("=" * 60)

    # Set env vars
    os.environ["LLM_PROVIDER"] = "openrouter"
    os.environ["LLM_API_KEY"] = "sk-test-openrouter"
    os.environ["LLM_API_URL"] = "https://openrouter.ai/api/v1/chat/completions"
    os.environ["LLM_MODEL"] = "nvidia/nemotron-3-super-120b-a12b:free"

    try:
        provider = create_llm_provider()
        print(f"  Provider name: {provider.provider_name}")
        print(f"  API URL: {provider.api_url}")
        print(f"  Model: {provider.model}")
        print(f"  [PASS] OpenRouter provider created successfully")
    except Exception as e:
        print(f"  [FAIL] {e}")

    print()


def test_provider_factory_volcano():
    """Test factory with Volcano config."""
    print("=" * 60)
    print("Test 3: Provider Factory - Volcano Engine")
    print("=" * 60)

    # Set env vars
    os.environ["LLM_PROVIDER"] = "volcano"
    os.environ["LLM_API_KEY"] = "5dda09ff-test-volcano"
    # Deliberately not setting URL and model to test defaults
    if "LLM_API_URL" in os.environ:
        del os.environ["LLM_API_URL"]
    if "LLM_MODEL" in os.environ:
        del os.environ["LLM_MODEL"]

    try:
        provider = create_llm_provider()
        print(f"  Provider name: {provider.provider_name}")
        print(f"  API URL: {provider.api_url}")
        print(f"  Model: {provider.model}")

        # Verify defaults
        assert "volces.com" in provider.api_url, "Should use Volcano URL"
        assert provider.model.startswith("ep-"), "Should use endpoint ID"
        print(f"  [PASS] Volcano provider created with correct defaults")
    except Exception as e:
        print(f"  [FAIL] {e}")

    print()


def test_provider_factory_no_key():
    """Test factory without API key."""
    print("=" * 60)
    print("Test 4: Provider Factory - No API Key")
    print("=" * 60)

    # Clear API key
    if "LLM_API_KEY" in os.environ:
        del os.environ["LLM_API_KEY"]
    if "VOLCANO_API_KEY" in os.environ:
        del os.environ["VOLCANO_API_KEY"]

    try:
        provider = create_llm_provider()
        print(f"  [FAIL] Should have raised ValueError")
    except ValueError as e:
        print(f"  [PASS] Correctly raised ValueError: {e}")
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")

    print()


def test_chat_service_integration():
    """Test that chat service can initialize provider."""
    print("=" * 60)
    print("Test 5: Chat Service Integration")
    print("=" * 60)

    # Restore a valid config
    os.environ["LLM_PROVIDER"] = "openrouter"
    os.environ["LLM_API_KEY"] = "sk-test-integration"
    os.environ["LLM_API_URL"] = "https://openrouter.ai/api/v1/chat/completions"
    os.environ["LLM_MODEL"] = "nvidia/nemotron-3-super-120b-a12b:free"

    try:
        from app.services.v2_llm import get_llm_service

        # Reset singleton
        import app.services.v2_llm as v2_llm_module
        v2_llm_module._llm_service = None

        service = get_llm_service()
        print(f"  Mock mode: {service._use_mock}")
        print(f"  Provider: {service._provider.provider_name if service._provider else 'None'}")
        print(f"  [PASS] Chat service initialized")
    except Exception as e:
        print(f"  [FAIL] {e}")

    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("LLM Provider Configuration Tests")
    print("=" * 60 + "\n")

    test_url_fix()
    test_provider_factory_openrouter()
    test_provider_factory_volcano()
    test_provider_factory_no_key()
    test_chat_service_integration()

    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)
