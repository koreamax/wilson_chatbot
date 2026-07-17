from collections.abc import AsyncIterator

from openai import AsyncOpenAI


class NvidiaNimProvider:
    """NVIDIA NIM(OpenAI 호환) 스트리밍 프로바이더.

    CLAUDE.md의 "LLM 프로바이더 추상화" 뒤에 위치한다 — 나중에 로컬/타사로 교체해도
    이 stream_tokens 인터페이스만 유지하면 servicer는 변경 없다.
    API 키는 생성자에서 env 유래 값만 받는다(실키를 코드에 두지 않는다).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens

    async def stream_tokens(
        self,
        system_prompt: str,
        user_text: str,
        context_chunks: list[str],
        language_code: str,
    ) -> AsyncIterator[str]:
        """토큰 델타를 순차 yield한다(외부 API 스트리밍)."""
        messages = _build_messages(system_prompt, user_text, context_chunks)
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            top_p=self._top_p,
            max_tokens=self._max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def _build_messages(
    system_prompt: str, user_text: str, context_chunks: list[str]
) -> list[dict]:
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if context_chunks:
        joined = "\n".join(f"- {chunk}" for chunk in context_chunks)
        messages.append({"role": "system", "content": f"참고 컨텍스트:\n{joined}"})
    messages.append({"role": "user", "content": user_text})
    return messages
