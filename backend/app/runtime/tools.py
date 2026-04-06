from typing import List, Optional

from app.services.asr_gateway import get_default_asr_gateway
from app.services.asr_types import AsrMediaInput, AsrProviderError, AsrTranscription


class MockTranscriptionUnavailable(Exception):
    pass


def transcribe_audio_input(
    *,
    media_ids: List[str],
    media_urls: List[str] | None = None,
    text_hint: Optional[str],
) -> AsrTranscription:
    try:
        gateway = get_default_asr_gateway()
        return gateway.transcribe(
            AsrMediaInput(
                media_ids=media_ids,
                media_urls=list(media_urls or []),
                text_hint=text_hint,
            )
        )
    except AsrProviderError as exc:
        raise MockTranscriptionUnavailable(exc.message) from exc
    except NotImplementedError as exc:
        raise MockTranscriptionUnavailable(str(exc)) from exc


def transcribe_audio(
    *,
    media_ids: List[str],
    media_urls: List[str] | None = None,
    text_hint: Optional[str],
) -> str:
    return transcribe_audio_input(media_ids=media_ids, media_urls=media_urls, text_hint=text_hint).text
