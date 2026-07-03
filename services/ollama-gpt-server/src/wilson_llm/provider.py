from collections.abc import AsyncIterator


class OllamaProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def stream_tokens(
        self,
        user_text: str,
        context_chunks: list[str],
        language_code: str,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("Ollama 토큰 스트리밍 연결 필요")
