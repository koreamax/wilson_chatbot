"""외부(BE→AI) DialogueService gRPC(aio) 진입점.

이 서버는 유일한 외부 수신 진입점이다(grpc.md). 내부적으로 RAG(①)·LLM(②) 유닛을 gRPC로
호출한다. 헬스체크 외 inbound REST는 만들지 않는다.
"""

from __future__ import annotations

import logging

import grpc

from wilson_orchestrator.adapters.llm_client import LlmClient
from wilson_orchestrator.adapters.rag_client import RagClient
from wilson_orchestrator.adapters.stt_client import SttClient
from wilson_orchestrator.generated import dialogue_pb2_grpc
from wilson_orchestrator.pipeline import DialoguePipeline, DialogueTurn
from wilson_orchestrator.settings import get_settings

logger = logging.getLogger(__name__)


class DialogueServicer(dialogue_pb2_grpc.DialogueServiceServicer):
    def __init__(self, pipeline: DialoguePipeline) -> None:
        self._pipeline = pipeline

    async def Converse(self, request, context: grpc.aio.ServicerContext):
        # 보안(security.md): 로그엔 추적 식별자만, 발화 원문·오디오는 남기지 않는다.
        logger.info(
            "Converse 수신 trace_id=%s session_id=%s turn_id=%s target_user_id=%s",
            request.trace_id,
            request.session_id,
            request.turn_id,
            request.target_user_id,
        )
        turn = DialogueTurn(
            trace_id=request.trace_id,
            target_user_id=request.target_user_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            audio_payload=request.audio_payload,
            audio_format=request.audio_format,
            language_code=request.language_code,
        )
        async for frame in self._pipeline.converse(turn):
            yield frame


async def serve() -> None:
    """Start the external DialogueService gRPC(aio) server."""
    settings = get_settings()

    if not settings.azure_speech_key:
        # 키가 없으면 STT가 실패한다. 조용히 넘기지 말고 크게 경고(실키는 로그에 안 남김).
        logger.error(
            "AZURE_SPEECH_KEY 미설정 — .env(로컬) 또는 K8s Secret에 키를 주입해야 STT가 동작합니다."
        )

    stt_client = SttClient(
        settings.azure_speech_key, settings.azure_speech_region, settings.language_code
    )
    rag_client = RagClient(settings.rag_server_target)
    llm_client = LlmClient(settings.llm_server_target)
    pipeline = DialoguePipeline(stt_client, rag_client, llm_client, settings)

    server = grpc.aio.server()
    dialogue_pb2_grpc.add_DialogueServiceServicer_to_server(DialogueServicer(pipeline), server)
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    await server.start()
    logger.info(
        "Orchestrator gRPC(aio) 서버 시작 %s:%s (rag=%s, llm=%s)",
        settings.grpc_host,
        settings.grpc_port,
        settings.rag_server_target,
        settings.llm_server_target,
    )
    await server.wait_for_termination()
