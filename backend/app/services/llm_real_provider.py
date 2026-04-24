"""LLM Provider for OpenAI-compatible API (supports Volcano, DeepSeek, etc.) with performance tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from json import JSONDecodeError
import os
import time
from typing import Any

import httpx


RETRYABLE_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
PERMANENT_REQUEST_ERRORS = (
    httpx.InvalidURL,
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
)


@dataclass(frozen=True)
class LLMMessage:
    """A message in the conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass(frozen=True)
class LLMCallStats:
    """Statistics for an LLM call."""
    provider: str
    model: str
    total_time_ms: float
    request_time_ms: float
    response_time_ms: float
    tokens_prompt: int
    tokens_completion: int
    tps: float
    success: bool
    error: str | None = None


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    role: str = "assistant"
    usage: dict[str, int] = field(default_factory=dict)
    stats: LLMCallStats | None = None


class LLMProviderError(Exception):
    """Raised when LLM call fails."""
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(f"[{code}] {message}")


class OpenAILLMProvider:
    """Generic OpenAI-compatible LLM Provider.
    
    Supports any provider using OpenAI API format:
    - Volcano Engine (火山引擎)
    - DeepSeek
    - Moonshot (Kimi)
    - OpenAI
    - Custom endpoints
    """
    
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_tokens: int = 500,
        temperature: float = 0.7,
        provider_name: str = "openai",
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.provider_name = provider_name
        self._http_session = self._create_session()
        self._last_stats: LLMCallStats | None = None
    
    def _create_session(self) -> httpx.Client:
        """Create HTTP session with connection pooling."""
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        return httpx.Client(
            limits=limits,
            timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
        )
    
    @property
    def last_stats(self) -> LLMCallStats | None:
        """Return stats from last call."""
        return self._last_stats
    
    def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> LLMResponse:
        """Send chat completion request.
        
        Args:
            messages: List of messages, each with "role" and "content"
            stream: Whether to stream the response
        
        Returns:
            LLMResponse with content and stats
        
        Raises:
            LLMProviderError: If the call fails
        """
        start_time = time.monotonic()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        # Optimize: shorten system prompts for speed
        optimized_messages = self._optimize_messages(messages)
        
        data = {
            "model": self.model,
            "messages": optimized_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": stream,
        }
        
        try:
            request_start = time.monotonic()
            response = self._http_session.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=self.timeout_seconds,
            )
            request_time = (time.monotonic() - request_start) * 1000
            
            response_start = time.monotonic()
            response.raise_for_status()
            
            try:
                result = response.json()
            except JSONDecodeError as exc:
                raise LLMProviderError(
                    "llm_response_parse_error",
                    f"Failed to parse response JSON: {exc}",
                    retryable=False,
                ) from exc
            
            response_time = (time.monotonic() - response_start) * 1000
            total_time = (time.monotonic() - start_time) * 1000
            
            # Extract content
            if "choices" not in result or not result["choices"]:
                raise LLMProviderError(
                    "llm_empty_choices",
                    "No choices in response",
                    retryable=True,
                )
            
            choice = result["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            role = message.get("role", "assistant")
            
            # Extract usage
            usage = result.get("usage", {})
            tokens_prompt = usage.get("prompt_tokens", 0)
            tokens_completion = usage.get("completion_tokens", 0)
            
            # Calculate TPS
            tps = tokens_completion / (total_time / 1000) if total_time > 0 else 0
            
            # Record stats
            self._last_stats = LLMCallStats(
                provider=self.provider_name,
                model=self.model,
                total_time_ms=total_time,
                request_time_ms=request_time,
                response_time_ms=response_time,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                tps=tps,
                success=True,
            )
            
            return LLMResponse(
                content=content,
                role=role,
                usage=usage,
                stats=self._last_stats,
            )
            
        except PERMANENT_REQUEST_ERRORS as exc:
            self._record_error(start_time, str(exc))
            raise LLMProviderError("llm_unavailable", str(exc), retryable=False) from exc
        except httpx.TimeoutException as exc:
            self._record_error(start_time, str(exc))
            raise LLMProviderError("llm_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            self._record_error(start_time, str(exc))
            raise LLMProviderError(
                "llm_unavailable",
                str(exc),
                retryable=self._is_retryable_http_error(exc),
            ) from exc
    
    def chat_stream(
        self,
        messages: list[dict[str, str]],
    ):
        """Send streaming chat completion request.
        
        Yields partial content chunks as they arrive.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/event-stream",
        }
        
        optimized_messages = self._optimize_messages(messages)
        
        data = {
            "model": self.model,
            "messages": optimized_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        
        with self._http_session.stream(
            "POST",
            self.api_url,
            headers=headers,
            json=data,
            timeout=self.timeout_seconds,
        ) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise LLMProviderError(
                    "llm_stream_error",
                    str(exc),
                    retryable=self._is_retryable_http_error(exc),
                ) from exc
            
            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                if line_str.startswith(":"):
                    continue
                
                if line_str.startswith("data: "):
                    json_str = line_str[6:]
                    if json_str == "[DONE]":
                        break
                    
                    try:
                        chunk = json.loads(json_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    
    def _optimize_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Optimize messages for performance.
        
        - Limit history to last 2 messages (reduce context tokens)
        - Keep system prompt concise
        """
        # Find system message
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        
        # Keep only recent messages for speed
        recent_history = other_msgs[-2:] if len(other_msgs) > 2 else other_msgs
        
        # Combine
        result = []
        if system_msgs:
            # Keep the first system message but make it concise
            system_content = system_msgs[0].get("content", "")
            # Truncate long system prompts
            if len(system_content) > 500:
                system_content = system_content[:500] + "..."
            result.append({"role": "system", "content": system_content})
        
        result.extend(recent_history)
        return result
    
    def _is_retryable_http_error(self, exc: httpx.HTTPError) -> bool:
        """Check if HTTP error is retryable."""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_HTTP_STATUS_CODES
        return False
    
    def _record_error(self, start_time: float, error: str):
        """Record error stats."""
        total_time = (time.monotonic() - start_time) * 1000
        self._last_stats = LLMCallStats(
            provider=self.provider_name,
            model=self.model,
            total_time_ms=total_time,
            request_time_ms=0,
            response_time_ms=0,
            tokens_prompt=0,
            tokens_completion=0,
            tps=0,
            success=False,
            error=error,
        )
    
    def close(self):
        """Close HTTP session."""
        self._http_session.close()


def _ensure_chat_completions_url(url: str) -> str:
    """Ensure URL points to /chat/completions endpoint.
    
    Many providers serve HTML dashboard at /v1 but API at /v1/chat/completions.
    """
    if not url:
        return url
    # If URL ends with /v1, append /chat/completions
    if url.rstrip("/").endswith("/v1"):
        return f"{url.rstrip('/')}/chat/completions"
    # If URL lacks both /v1 and /chat/completions, assume it's a base URL
    if "/v1" not in url and "/chat/completions" not in url:
        return f"{url.rstrip('/')}/v1/chat/completions"
    return url


def create_llm_provider(
    api_key: str | None = None,
    model: str | None = None,
    api_url: str | None = None,
    provider_name: str | None = None,
    timeout_seconds: float = 30.0,
    max_tokens: int = 500,
    temperature: float = 0.7,
) -> OpenAILLMProvider:
    """Factory function to create LLM provider from env vars or args.
    
    Supports multiple provider configurations via environment variables:
    - LLM_API_URL / LLM_API_KEY / LLM_MODEL (generic)
    - VOLCANO_API_URL / VOLCANO_API_KEY / VOLCANO_MODEL
    
    Auto-fixes URLs to ensure they point to /chat/completions endpoint.
    
    Priority:
    1. Explicit arguments
    2. Environment variables (prefixed then generic)
    3. Raise error if not configured
    """
    import os
    
    # Config priority: explicit args > env vars > defaults
    _api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("VOLCANO_API_KEY")
    _model = model or os.getenv("LLM_MODEL") or os.getenv("VOLCANO_MODEL") or "kimi-k2.6"
    _api_url = api_url or os.getenv("LLM_API_URL") or os.getenv("VOLCANO_API_URL", "https://gptrr.qzz.io/v1/chat/completions")
    _provider_name = provider_name or os.getenv("LLM_PROVIDER_NAME", "custom")
    
    # Auto-fix URL to ensure full /v1/chat/completions path
    _api_url = _ensure_chat_completions_url(_api_url)
    
    if not _api_key:
        raise ValueError(
            "LLM API key required. Set LLM_API_KEY or VOLCANO_API_KEY env var.\n"
            "Example: export LLM_API_KEY=sk-xxxxx"
        )
    
    return OpenAILLMProvider(
        api_url=_api_url,
        api_key=_api_key,
        model=_model,
        provider_name=_provider_name,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        temperature=temperature,
    )


# Legacy alias for backward compatibility
VolcanoLLMProvider = OpenAILLMProvider
create_volcano_provider = create_llm_provider
