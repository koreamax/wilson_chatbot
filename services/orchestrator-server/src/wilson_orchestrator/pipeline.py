"""대화 파이프라인 — STT → RAG → LLM → TTS 조율.

Phase 1(텍스트 스파인): 실제 STT/TTS는 아직 연결하지 않는다. 입력 오디오 바이트를 UTF-8
텍스트로 해석하는 임시 브리지로 전 구간(③→①→②)을 잇고, 출력은 오디오 청크 없이
Metadata→Completion 프레임으로 흘린다. Phase 2에서 STT/TTS를 이 자리에 끼운다.

프레임 계약은 grpc.md 소유: 첫 프레임은 MetadataFrame, 정상 종료는 CompletionFrame,
실패는 gRPC status로 스트림을 끊지 않고 ErrorFrame을 흘린 뒤 정상 종료한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging

from wilson_orchestrator.adapters.llm_client import LlmClient
from wilson_orchestrator.adapters.rag_client import RagClient
from wilson_orchestrator.generated import dialogue_pb2
from wilson_orchestrator.settings import Settings

logger = logging.getLogger(__name__)


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
    def __init__(self, rag_client: RagClient, llm_client: LlmClient, settings: Settings) -> None:
        self._rag = rag_client
        self._llm = llm_client
        self._settings = settings

    async def converse(self, turn: DialogueTurn) -> AsyncIterator[dialogue_pb2.StreamResponse]:
        # --- STT (Phase 1 임시 브리지: 오디오 바이트를 UTF-8 텍스트로 해석) ---
        try:
            stt_text = turn.audio_payload.decode("utf-8").strip()
        except UnicodeDecodeError:
            # 실제 오디오가 들어온 경우 — STT 미연결이라 아직 처리할 수 없다.
            logger.warning(
                "STT 미연결(Phase 1): 오디오 바이트를 텍스트로 해석 불가. trace_id=%s turn_id=%s",
                turn.trace_id,
                turn.turn_id,
            )
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

        # --- LLM 토큰 스트림 누적 (Phase 1: TTS 없음 → 오디오 청크 미전송) ---
        # LLM 스트리밍은 내부(③↔②)에서 실제로 소비하되, TTS가 없어 외부로는 청크를 흘리지
        # 않고 완성 텍스트만 CompletionFrame에 담는다. Phase 2에서 이 토큰을 TTS로 흘린다.
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

        # 프레임 N+1: 정상 종료 — 완성된 전체 텍스트를 1회 전달(grpc.md, 조각내지 않는다).
        yield dialogue_pb2.StreamResponse(
            completion=dialogue_pb2.CompletionFrame(
                full_llm_response_text="".join(response_parts)
            )
        )


def _error_frame(stage: int, full_text: str) -> dialogue_pb2.StreamResponse:
    # recoverable: Phase 1은 오디오 청크를 전송하지 않으므로 앱이 재생할 부분분이 없다 → False.
    return dialogue_pb2.StreamResponse(
        error=dialogue_pb2.ErrorFrame(
            error_stage=stage,
            recoverable=False,
            full_llm_response_text=full_text,
        )
    )
