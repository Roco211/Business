from typing import List, Optional

MOCK_TRANSCRIPTS = {
    "voice_query_demo": "check stock left for cola",
    "voice_stock_in_demo": "restock apples today",
    "voice_stock_out_demo": "stock out cola for walk in sale",
}


class MockTranscriptionUnavailable(Exception):
    pass


def transcribe_audio(*, media_ids: List[str], text_hint: Optional[str]) -> str:
    if text_hint:
        stripped = text_hint.strip()
        if stripped:
            return stripped
    if media_ids:
        first_media = media_ids[0]
        if first_media in MOCK_TRANSCRIPTS:
            return MOCK_TRANSCRIPTS[first_media]
    raise MockTranscriptionUnavailable("mock transcription unavailable")
