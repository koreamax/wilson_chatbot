"""TTS 어댑터 — Azure Speech TTS(REST)로 응답 텍스트를 음성 바이트로 합성.

STT와 동일 Azure Speech 리소스(key·region)를 재사용한다 — 신규 자격증명 없음.
security.md 준수: 리전은 한국(koreacentral) 고정, 응답 텍스트·오디오는 로그에 남기지 않는다.
Google TTS는 한국 리전 엔드포인트 미지원으로 배제됨(stt-tts.md/security.md).
"""

from __future__ import annotations

from xml.sax.saxutils import escape

import httpx


class TtsError(RuntimeError):
    """TTS 합성 실패 — 파이프라인이 ErrorFrame(ERROR_STAGE_TTS)로 변환한다."""


class TtsClient:
    def __init__(self, api_key: str, region: str, voice: str, output_format: str) -> None:
        self._api_key = api_key
        self._voice = voice
        self._output_format = output_format
        self._url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self._client = httpx.AsyncClient(timeout=15.0)

    async def synthesize(self, text: str) -> bytes:
        """한 문장(또는 세그먼트)을 음성 바이트로 합성한다. 오케스트레이터가 청크로 흘린다."""
        # SSML 본문 — 응답 텍스트는 XML 특수문자(&,<,>)를 이스케이프해야 SSML이 깨지지 않는다.
        ssml = (
            "<speak version='1.0' xml:lang='ko-KR'>"
            f"<voice name='{self._voice}'>{escape(text)}</voice></speak>"
        )
        try:
            response = await self._client.post(
                self._url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._api_key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": self._output_format,
                    "User-Agent": "wilson-orchestrator",
                },
                content=ssml.encode("utf-8"),
            )
        except httpx.HTTPError as exc:
            # 응답 텍스트·오디오는 남기지 않는다. 예외 종류까지만.
            raise TtsError(f"TTS 요청 실패: {type(exc).__name__}") from exc

        if response.status_code != 200:
            raise TtsError(f"TTS HTTP {response.status_code}")
        return response.content

    async def close(self) -> None:
        await self._client.aclose()
