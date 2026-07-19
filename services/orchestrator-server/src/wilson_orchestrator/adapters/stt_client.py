"""STT 어댑터 — Azure Speech(short-audio REST)로 발화 오디오를 텍스트로 전사.

security.md 준수: 리전은 한국(koreacentral) 고정, 원본 음성은 인메모리 처리(디스크 기록 안 함),
전사 텍스트·오디오는 로그에 남기지 않는다(추적 식별자만). grpc.md 정합: 입력은 발화 종료 후
단일 bytes(스트리밍 입력 아님), audio_format은 힌트로만 쓰고 실제 바이트로 포맷을 판별한다.
"""

from __future__ import annotations

import httpx


class SttError(RuntimeError):
    """STT 전사 실패 — 파이프라인이 ErrorFrame(ERROR_STAGE_STT)로 변환한다."""


def _content_type(audio_payload: bytes) -> str:
    """실제 바이트로 컨테이너를 판별해 Azure content-type을 고른다(audio_format 힌트 불신).

    short-audio REST가 네이티브 지원하는 컨테이너만 처리한다. m4a/AAC 등 미지원 코덱은
    여기서 실패시키고, 트랜스코딩/Speech SDK 경로는 후속 과제로 둔다. [구현 시 검증]
    """
    if audio_payload[:4] == b"RIFF" and audio_payload[8:12] == b"WAVE":
        return "audio/wav; codecs=audio/pcm"
    if audio_payload[:4] == b"OggS":
        return "audio/ogg; codecs=opus"
    raise SttError("지원하지 않는 오디오 포맷(현재 WAV/OGG-OPUS만). 실제 바이트 헤더 불일치.")


class SttClient:
    def __init__(self, api_key: str, region: str, language_code: str) -> None:
        self._api_key = api_key
        self._language = language_code
        self._url = (
            f"https://{region}.stt.speech.microsoft.com"
            "/speech/recognition/conversation/cognitiveservices/v1"
        )
        self._client = httpx.AsyncClient(timeout=15.0)

    async def transcribe(self, audio_payload: bytes, audio_format: str) -> str:
        if not audio_payload:
            raise SttError("빈 오디오 페이로드.")
        content_type = _content_type(audio_payload)  # 힌트(audio_format) 대신 실제 바이트로 판별
        try:
            response = await self._client.post(
                self._url,
                params={"language": self._language, "format": "detailed"},
                headers={
                    "Ocp-Apim-Subscription-Key": self._api_key,
                    "Content-Type": content_type,
                    "Accept": "application/json",
                },
                content=audio_payload,
            )
        except httpx.HTTPError as exc:
            # 발화 원문·오디오는 남기지 않는다. 예외 종류까지만.
            raise SttError(f"STT 요청 실패: {type(exc).__name__}") from exc

        if response.status_code != 200:
            raise SttError(f"STT HTTP {response.status_code}")

        body = response.json()
        if body.get("RecognitionStatus") != "Success":
            raise SttError(f"STT 인식 실패: {body.get('RecognitionStatus')}")
        # 대화용 텍스트는 DisplayText(정규화). 인지지표(Phase 4)는 NBest[].Lexical 사용 예정.
        return body.get("DisplayText", "")

    async def close(self) -> None:
        await self._client.aclose()
