from typing import List, Optional

from app.services.asr_gateway import get_default_asr_gateway
from app.services.asr_types import AsrMediaInput, AsrProviderError


class MockTranscriptionUnavailable(Exception):
    pass


def transcribe_audio(*, media_ids: List[str], text_hint: Optional[str]) -> str:
    try:
        gateway = get_default_asr_gateway()
        transcription = gateway.transcribe(AsrMediaInput(media_ids=media_ids, text_hint=text_hint))
    except AsrProviderError as exc:
        raise MockTranscriptionUnavailable(exc.message) from exc
    except NotImplementedError as exc:
        raise MockTranscriptionUnavailable(str(exc)) from exc
    return transcription.text
