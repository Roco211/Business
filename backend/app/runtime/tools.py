from typing import Sequence

MOCK_TRANSCRIPTS = {
    "fixture-query": "how much is jade today?",
}


class MockTranscriptionUnavailable(Exception):
    pass


def transcribe_audio(text_hint: str, media_ids: Sequence[str]) -> str:
    if text_hint:
        return text_hint
    for media_id in media_ids or []:
        if media_id in MOCK_TRANSCRIPTS:
            return MOCK_TRANSCRIPTS[media_id]
    raise MockTranscriptionUnavailable("mock transcription unavailable")
