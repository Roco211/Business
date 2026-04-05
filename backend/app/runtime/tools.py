from typing import List, Optional

from app.services.asr_gateway import get_default_asr_gateway
from app.services.asr_mock_provider import MOCK_TRANSCRIPTS
from app.services.asr_types import AsrMediaInput, AsrProviderError

class MockTranscriptionUnavailable(Exception):
    pass


def transcribe_audio(*, media_ids: List[str], text_hint: Optional[str]) -> str:
    gateway = get_default_asr_gateway()
    try:
        transcription = gateway.transcribe(AsrMediaInput(media_ids=media_ids, text_hint=text_hint))
    except AsrProviderError as exc:
        raise MockTranscriptionUnavailable(exc.message) from exc
    return transcription.text
