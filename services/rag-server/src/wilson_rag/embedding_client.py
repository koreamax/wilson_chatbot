class EmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("임베딩 모델 연결 필요")
