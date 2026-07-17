"""라이브 스모크 — .env의 NVIDIA_API_KEY로 NVIDIA NIM에 실제 호출, 한국어 응답 스트리밍 확인.

사용: PYTHONPATH=services/ollama-gpt-server/src, .env에 키 설정 후
      python services/ollama-gpt-server/scripts/smoke_live.py
"""

import asyncio

from wilson_llm.provider import NvidiaNimProvider
from wilson_llm.settings import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.nvidia_api_key:
        raise SystemExit("NVIDIA_API_KEY 미설정 — .env에 키를 넣어주세요.")

    provider = NvidiaNimProvider(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        top_p=settings.llm_top_p,
        max_tokens=settings.llm_max_tokens,
    )
    print(f"model={settings.llm_model}\n---")
    async for token in provider.stream_tokens(
        system_prompt="당신은 치매 어르신을 돕는 부드럽고 비판단적인 케어 도우미입니다.",
        user_text="약 언제 먹어요?",
        context_chunks=["복약 안내: 아침 8시, 저녁 7시"],
        language_code="ko-KR",
    ):
        print(token, end="", flush=True)
    print("\n---\nOK")


if __name__ == "__main__":
    asyncio.run(main())
