class LlmClient:
    async def stream_tokens(self, user_text: str, context_chunks: list[str]):
        raise NotImplementedError("LLM 서버 gRPC client 연결 필요")
