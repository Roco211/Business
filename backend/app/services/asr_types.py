from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AsrMediaInput:
    media_ids: list[str]
    text_hint: str | None = None


@dataclass(frozen=True)
class AsrTranscription:
    text: str
    provider: str
    confidence: float | None = None


class AsrProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class AsrProvider(Protocol):
    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        ...
