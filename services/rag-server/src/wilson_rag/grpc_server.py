from concurrent import futures
import logging

import grpc

from wilson_rag.chroma_collections import ChromaCollection
from wilson_rag.config.settings import Settings, get_settings
from wilson_rag.context_builder import ContextBuilder
from wilson_rag.embedding_client import EmbeddingClient
from wilson_rag.generated import rag_pb2, rag_pb2_grpc
from wilson_rag.infrastructure.chroma_client import create_chroma_client, wait_for_chroma
from wilson_rag.repository import ChromaRepository, SearchHit

logger = logging.getLogger(__name__)

# proto ChromaCollection enum → 내부 StrEnum. UNSPECIFIED는 매핑하지 않는다(무시).
_PROTO_TO_COLLECTION: dict[int, ChromaCollection] = {
    rag_pb2.STATIC_KNOWLEDGE: ChromaCollection.STATIC_KNOWLEDGE,
    rag_pb2.ELDER: ChromaCollection.ELDER,
    rag_pb2.GUARDIAN: ChromaCollection.GUARDIAN,
}

_PUBLIC_COLLECTIONS = frozenset({ChromaCollection.STATIC_KNOWLEDGE})


class RagServicer(rag_pb2_grpc.RagServiceServicer):
    """RagService.BuildContext 구현 (3단계: dense 검색).

    query_text를 ruri-v3로 임베딩해 요청된 컬렉션을 dense 검색하고, 결과를 조립해
    반환한다. static_knowledge(public)만 스코프 없이 검색하며, elder/guardian(private)은
    스코프 필터가 설정되기 전까지 검색하지 않는다(개인정보 유출 방지). BM25/RRF는 4단계.
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        repository: ChromaRepository,
        context_builder: ContextBuilder,
        top_k: int,
        scope_metadata_field: str,
    ) -> None:
        self._embedding = embedding_client
        self._repository = repository
        self._context_builder = context_builder
        self._top_k = top_k
        self._scope_field = scope_metadata_field

    def BuildContext(
        self,
        request: rag_pb2.BuildContextRequest,
        context: grpc.ServicerContext,
    ) -> rag_pb2.BuildContextResponse:
        # 보안(security.md): 로그에는 추적 식별자만, 발화 원문(query_text)은 남기지 않는다.
        logger.info(
            "BuildContext 수신 trace_id=%s turn_id=%s target_user_id=%s session_id=%s collections=%d",
            request.trace_id,
            request.turn_id,
            request.target_user_id,
            request.session_id,
            len(request.collections),
        )

        query_embedding = self._embedding.embed_query(request.query_text)

        hits: list[SearchHit] = []
        for collection in self._resolve_collections(request.collections):
            should_search, where = self._scope(collection, request.target_user_id)
            if not should_search:
                logger.warning(
                    "스코프 미설정으로 private 컬렉션 '%s' 검색을 건너뜁니다.",
                    collection.value,
                )
                continue
            try:
                hits.extend(
                    self._repository.dense_search(
                        collection, query_embedding, self._top_k, where=where
                    )
                )
            except Exception:
                # rag.md 폴백: 검색 실패해도 대화 루프는 유지한다. 해당 컬렉션만 건너뛴다.
                logger.exception("컬렉션 '%s' 검색 실패", collection.value)

        chunks, fallback_used = self._context_builder.assemble(hits)
        return rag_pb2.BuildContextResponse(
            chunks=[_to_proto_chunk(chunk) for chunk in chunks],
            fallback_used=fallback_used,
        )

    def _resolve_collections(self, proto_collections) -> list[ChromaCollection]:
        resolved: list[ChromaCollection] = []
        for value in proto_collections:
            collection = _PROTO_TO_COLLECTION.get(value)
            if collection is None:
                logger.warning("알 수 없는 컬렉션 enum 값 무시: %s", value)
                continue
            resolved.append(collection)
        return resolved

    def _scope(
        self, collection: ChromaCollection, target_user_id: str
    ) -> tuple[bool, dict | None]:
        """(검색 여부, where 필터)를 돌려준다.

        public은 필터 없이 검색. private는 스코프 필드+식별자가 있어야만 검색하고,
        없으면 검색하지 않는다(스코프 없는 private 검색 금지 — rag.md).
        """
        if collection in _PUBLIC_COLLECTIONS:
            return True, None
        if self._scope_field and target_user_id:
            return True, {self._scope_field: target_user_id}
        return False, None


def _to_proto_chunk(hit: SearchHit) -> rag_pb2.ContextChunk:
    return rag_pb2.ContextChunk(
        collection=hit.collection.value,
        document_id=hit.document_id,
        text=hit.text,
        score=hit.score,
    )


def _build_servicer(settings: Settings, repository: ChromaRepository) -> RagServicer:
    return RagServicer(
        embedding_client=EmbeddingClient(settings.embedding_model_name),
        repository=repository,
        context_builder=ContextBuilder(),
        top_k=settings.search_top_k,
        scope_metadata_field=settings.scope_metadata_field,
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
        _build_servicer(settings, repository),
        server,
    )
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    server.start()
    logger.info("RAG gRPC server listening on %s:%s", settings.grpc_host, settings.grpc_port)
    server.wait_for_termination()
