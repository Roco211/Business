from app.services.asr_types import AsrMediaInput, AsrProviderError, AsrTranscription

MOCK_TRANSCRIPTS = {
    "voice_query_demo": "check stock left for cola",
    "voice_stock_in_demo": "restock apples today",
    "voice_stock_out_demo": "stock out cola for walk in sale",
}


class MockAsrProvider:
    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        if media_input.text_hint:
            stripped = media_input.text_hint.strip()
            if stripped:
                return AsrTranscription(text=stripped, provider="mock")

        for media_id in media_input.media_ids:
            transcript = MOCK_TRANSCRIPTS.get(media_id)
            if transcript:
                return AsrTranscription(text=transcript, provider="mock")

        raise AsrProviderError(
            "asr_unavailable",
            "mock transcription unavailable",
            retryable=False,
        )

