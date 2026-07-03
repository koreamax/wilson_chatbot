from concurrent import futures
import logging

import grpc

from wilson_rag.config.settings import get_settings
from wilson_rag.context_builder import ContextBuilder, RagContextChunk
from wilson_rag.generated import rag_pb2, rag_pb2_grpc
from wilson_rag.infrastructure.chroma_client import create_chroma_client, wait_for_chroma
from wilson_rag.repository import ChromaRepository

logger = logging.getLogger(__name__)


class RagServicer(rag_pb2_grpc.RagServiceServicer):
    """RagService.BuildContext 구현.

    2단계 골격: 요청을 받아 계약대로 응답을 돌려주는 껍데기다. 아직 검색(dense/BM25/RRF)
    은 배선하지 않고 폴백 컨텍스트(빈 chunks + fallback_used=True)를 반환한다.
    검색 로직과 스코프 필터는 3단계에서 repository/embedding을 주입해 채운다.
    """

    def __init__(self, context_builder: ContextBuilder) -> None:
        self._context_builder = context_builder

    def BuildContext(
        self,
        request: rag_pb2.BuildContextRequest,
        context: grpc.ServicerContext,
    ) -> rag_pb2.BuildContextResponse:
        # 보안(security.md): 로그에는 추적 식별자만 남기고 발화 원문(query_text)은 남기지 않는다.
        logger.info(
            "BuildContext 수신 trace_id=%s turn_id=%s target_user_id=%s session_id=%s collections=%d",
            request.trace_id,
            request.turn_id,
            request.target_user_id,
            request.session_id,
            len(request.collections),
        )

        # ASSUMPTION(2단계): 검색 미배선이므로 항상 폴백. 3단계에서 검색→폴백 조건 분기로 대체.
        chunks = self._context_builder.build_fallback()
        return rag_pb2.BuildContextResponse(
            chunks=[_to_proto_chunk(chunk) for chunk in chunks],
            fallback_used=True,
        )


def _to_proto_chunk(chunk: RagContextChunk) -> rag_pb2.ContextChunk:
    return rag_pb2.ContextChunk(
        collection=chunk.collection.value,
        document_id=chunk.document_id,
        text=chunk.text,
        score=chunk.score,
    )


def serve() -> None:
    """Start the RAG gRPC server."""
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    chroma_client = create_chroma_client(settings)
    wait_for_chroma(chroma_client, settings.chroma_connect_timeout_seconds)
    repository = ChromaRepository(chroma_client)
    repository.ensure_required_collections()
    logger.info("ChromaDB connected. Collections: %s", repository.collection_names())

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rag_pb2_grpc.add_RagServiceServicer_to_server(
        RagServicer(context_builder=ContextBuilder()),
        server,
    )
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    server.start()
    logger.info("RAG gRPC server listening on %s:%s", settings.grpc_host, settings.grpc_port)
    server.wait_for_termination()
