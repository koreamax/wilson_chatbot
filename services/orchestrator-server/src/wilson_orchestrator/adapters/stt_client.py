class SttClient:
    async def transcribe(self, audio_payload: bytes, audio_format: str, language_code: str) -> str:
        raise NotImplementedError("클라우드 STT API 연결 필요")
