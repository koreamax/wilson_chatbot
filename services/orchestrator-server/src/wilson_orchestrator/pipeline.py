"""대화 파이프라인 — STT → RAG → LLM → TTS 조율.

STT는 Azure Speech(#22), TTS는 Azure Speech(#24)로 연결됨(동일 리소스 재사용).
LLM 응답을 문장 단위로 TTS 합성해 AudioChunk로 스트리밍한다.

프레임 계약은 grpc.md 소유: 첫 프레임은 MetadataFrame, 오디오는 AudioChunk(sequence),
정상 종료는 CompletionFrame, 실패는 gRPC status로 스트림을 끊지 않고 ErrorFrame을 흘린 뒤
정상 종료한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
import re

from wilson_orchestrator.adapters.llm_client import LlmClient
from wilson_orchestrator.adapters.rag_client import RagClient
from wilson_orchestrator.adapters.stt_client import SttClient
from wilson_orchestrator.adapters.tts_client import TtsClient
from wilson_orchestrator.generated import dialogue_pb2
from wilson_orchestrator.settings import Settings

logger = logging.getLogger(__name__)

# 종결부호 뒤 공백에서 문장을 나눈다. 부호가 없으면 전체가 한 문장(단일 발화)으로 처리된다.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…。])\s+")


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text.strip()) if part.strip()]


@dataclass(frozen=True)
class DialogueTurn:
    trace_id: str
    target_user_id: str
    session_id: str
    turn_id: str
    audio_payload: bytes
    audio_format: str
    language_code: str


class DialoguePipeline:
    def __init__(
        self,
        stt_client: SttClient,
        rag_client: RagClient,
        llm_client: LlmClient,
        tts_client: TtsClient,
        settings: Settings,
    ) -> None:
        self._stt = stt_client
        self._rag = rag_client
        self._llm = llm_client
        self._tts = tts_client
        self._settings = settings

    async def converse(self, turn: DialogueTurn) -> AsyncIterator[dialogue_pb2.StreamResponse]:
        # --- STT (Azure Speech) ---
        try:
            stt_text = (await self._stt.transcribe(turn.audio_payload, turn.audio_format)).strip()
        except Exception:
            # STT 실패는 대화 응답을 못 만든다 → ErrorFrame(STT)로 우아하게 종료(grpc.md).
            logger.exception(
                "STT 전사 실패 — ErrorFrame(STT)로 종료. trace_id=%s turn_id=%s",
                turn.trace_id,
                turn.turn_id,
            )
            yield _error_frame(dialogue_pb2.ERROR_STAGE_STT, "")
            return

        # 빈/공백 발화 방어(1차 방어는 BE). 빈 입력으로 RAG·LLM을 낭비하지 않는다.
        if not stt_text:
            logger.info("빈 발화 — 처리 생략. trace_id=%s turn_id=%s", turn.trace_id, turn.turn_id)
            yield _error_frame(dialogue_pb2.ERROR_STAGE_STT, "")
            return

        # 프레임 1: STT 결과 선전송(grpc.md — 반드시 첫 프레임).
        yield dialogue_pb2.StreamResponse(
            metadata=dialogue_pb2.MetadataFrame(stt_text=stt_text)
        )

        # --- RAG (검색 실패는 대화를 끊지 않는다: rag.md 폴백) ---
        context_chunks: list[str] = []
        try:
            rag_context = await self._rag.build_context(
                trace_id=turn.trace_id,
                turn_id=turn.turn_id,
                target_user_id=turn.target_user_id,
                session_id=turn.session_id,
                query_text=stt_text,
            )
            context_chunks = rag_context.chunk_texts
        except Exception:
            logger.exception(
                "RAG BuildContext 실패 — 폴백(빈 컨텍스트)으로 진행. trace_id=%s turn_id=%s",
                turn.trace_id,
                turn.turn_id,
            )

        # --- LLM 토큰 스트림 누적 ---
        response_parts: list[str] = []
        try:
            async for token in self._llm.stream_tokens(
                trace_id=turn.trace_id,
                turn_id=turn.turn_id,
                system_prompt=self._settings.system_prompt,
                user_text=stt_text,
                context_chunks=context_chunks,
                language_code=turn.language_code or self._settings.language_code,
            ):
                response_parts.append(token)
        except Exception:
            logger.exception(
                "LLM Generate 실패 — ErrorFrame으로 종료. trace_id=%s turn_id=%s",
                turn.trace_id,
                turn.turn_id,
            )
            yield _error_frame(dialogue_pb2.ERROR_STAGE_LLM, "".join(response_parts))
            return

        full_text = "".join(response_parts)

        # --- TTS (문장 단위 순차 합성 → AudioChunk 스트리밍) ---
        # 문장이 완성되는 대로 합성해 청크를 흘린다(전체 대기 후 일괄 전송 금지, grpc.md).
        # 오버랩(LLM↔TTS 겹침)은 후속 최적화 — 여기서는 LLM 완료 후 문장별 순차.
        sequence = 0
        try:
            for sentence in _split_sentences(full_text):
                audio = await self._tts.synthesize(sentence)
                if not audio:
                    continue
                sequence += 1
                yield dialogue_pb2.StreamResponse(
                    audio_chunk=dialogue_pb2.AudioChunk(data=audio, sequence=sequence)
                )
        except Exception:
            # TTS 실패해도 텍스트는 완성됐으므로 full_llm_response_text를 실어 이력을 보존한다.
            # 이미 보낸 청크(sequence>0)가 있으면 앱이 그만큼 재생 가능 → recoverable=True.
            logger.exception(
                "TTS 합성 실패 — ErrorFrame(TTS)으로 종료. trace_id=%s turn_id=%s",
                turn.trace_id,
                turn.turn_id,
            )
            yield _error_frame(
                dialogue_pb2.ERROR_STAGE_TTS, full_text, recoverable=sequence > 0
            )
            return

        # 프레임 N+1: 정상 종료 — 완성된 전체 텍스트를 1회 전달(grpc.md, 조각내지 않는다).
        yield dialogue_pb2.StreamResponse(
            completion=dialogue_pb2.CompletionFrame(full_llm_response_text=full_text)
        )


def _error_frame(
    stage: int, full_text: str, recoverable: bool = False
) -> dialogue_pb2.StreamResponse:
    # recoverable: 이미 전송한 오디오 청크가 있어 앱이 부분 재생 가능한지(앱 폴백 판단용).
    return dialogue_pb2.StreamResponse(
        error=dialogue_pb2.ErrorFrame(
            error_stage=stage,
            recoverable=recoverable,
            full_llm_response_text=full_text,
        )
    )
