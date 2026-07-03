class TtsClient:
    async def synthesize_stream(self, text_stream):
        raise NotImplementedError("클라우드 TTS API 연결 필요")
