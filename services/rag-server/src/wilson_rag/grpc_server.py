from concurrent import futures
from datetime import datetime, timezone
import logging

import grpc

from wilson_rag.bm25_index import Bm25Index
from wilson_rag.chroma_collections import ChromaCollection
from wilson_rag.config.settings import Settings, get_settings
from wilson_rag.context_builder import ContextBuilder
from wilson_rag.embedding_client import EmbeddingClient
from wilson_rag.generated import rag_pb2, rag_pb2_grpc
from wilson_rag.infrastructure.chroma_client import create_chroma_client, wait_for_chroma
from wilson_rag.kiwi_tokenizer import KiwiTokenizer
from wilson_rag.repository import ChromaRepository, SearchHit, SparseIndexProtocol

logger = logging.getLogger(__name__)

# proto ChromaCollection enum → 내부 StrEnum. UNSPECIFIED는 매핑하지 않는다(무시).
_PROTO_TO_COLLECTION: dict[int, ChromaCollection] = {
    rag_pb2.STATIC_KNOWLEDGE: ChromaCollection.STATIC_KNOWLEDGE,
    rag_pb2.ELDER: ChromaCollection.ELDER,
    rag_pb2.GUARDIAN: ChromaCollection.GUARDIAN,
}


class RagServicer(rag_pb2_grpc.RagServiceServicer):
    """RagService 구현 — BuildContext(read, 하이브리드)와 StoreConversation(write, elder).

    read: query_text를 KURE-v1로 임베딩해 요청 컬렉션을 하이브리드(dense+BM25 RRF) 검색.
      static_knowledge는 기동 시 만든 공유 BM25 색인을, elder는 그 노인 문서로만 요청별로
      지은 스코프 BM25 색인을 쓴다(스코프된 문서로만 지어 유출 불가). guardian은 ERD 미확정이라
      검색하지 않는다.
    write: 세션 종료 후 오케스트레이터가 호출. 대화 턴(STT텍스트+LLM응답)을 문서 임베딩해
      elder 컬렉션에 스코프 메타데이터와 함께 저장.
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        repository: ChromaRepository,
        context_builder: ContextBuilder,
        top_k: int,
        scope_metadata_field: str,
        tokenizer: KiwiTokenizer,
        static_sparse_indexes: dict[ChromaCollection, SparseIndexProtocol],
    ) -> None:
        self._embedding = embedding_client
        self._repository = repository
        self._context_builder = context_builder
        self._top_k = top_k
        self._scope_field = scope_metadata_field
        self._tokenizer = tokenizer
        self._static_sparse = static_sparse_indexes

    # ---- read ----------------------------------------------------------------

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

        try:
            query_embedding = self._embedding.embed_query(request.query_text)
        except Exception:
            # rag.md 폴백: 임베딩 실패도 검색 실패다. RPC를 끊지 말고 폴백으로 대화를 유지한다.
            logger.exception(
                "임베딩 실패 — 폴백으로 응답합니다. trace_id=%s turn_id=%s",
                request.trace_id,
                request.turn_id,
            )
            return rag_pb2.BuildContextResponse(chunks=[], fallback_used=True)

        hits: list[SearchHit] = []
        for collection in self._resolve_collections(request.collections):
            should_search, where = self._scope(collection, request.target_user_id)
            if not should_search:
                logger.warning("컬렉션 '%s' 검색을 건너뜁니다(스코프 미충족).", collection.value)
                continue
            try:
                sparse_index = self._sparse_index_for(collection, where)
                hits.extend(
                    self._repository.hybrid_search(
                        collection,
                        request.query_text,
                        query_embedding,
                        self._top_k,
                        where=where,
                        sparse_index=sparse_index,
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
        """(검색 여부, where 필터)를 돌려준다."""
        if collection == ChromaCollection.STATIC_KNOWLEDGE:
            return True, None  # public, 필터 없음
        if collection == ChromaCollection.ELDER:
            # 노인별 스코프. 스코프 필드+식별자가 있어야만 검색(없으면 유출 방지 위해 스킵).
            if self._scope_field and target_user_id:
                return True, {self._scope_field: target_user_id}
            return False, None
        # guardian: 보호자 식별자·권한 매핑이 ERD 미확정이라 아직 검색하지 않는다.
        return False, None

    def _sparse_index_for(
        self, collection: ChromaCollection, where: dict | None
    ) -> SparseIndexProtocol | None:
        """이 검색에 쓸 BM25 색인을 고른다.

        public(static_knowledge)은 기동 시 만든 공유 색인. elder는 그 노인 문서로만 요청별로
        즉석 빌드(명사 토큰화, 고유명사 중심). 스코프된 문서로만 지어지므로 유출이 불가능하다.
        """
        static_index = self._static_sparse.get(collection)
        if static_index is not None:
            return static_index
        if collection == ChromaCollection.ELDER and where is not None:
            documents = self._repository.load_documents(collection, where=where)
            index = Bm25Index(self._tokenizer.tokenize)
            index.build(documents)
            return index
        return None

    # ---- write ---------------------------------------------------------------

    def StoreConversation(
        self,
        request: rag_pb2.StoreConversationRequest,
        context: grpc.ServicerContext,
    ) -> rag_pb2.StoreConversationResponse:
        # 보안: 추적 식별자·건수만 로깅, 발화 원문은 남기지 않는다.
        logger.info(
            "StoreConversation 수신 trace_id=%s target_user_id=%s session_id=%s turns=%d",
            request.trace_id,
            request.target_user_id,
            request.session_id,
            len(request.turns),
        )

        # 스코프 키가 없으면 저장을 거부한다. 빈 키로 저장하면 read가 스코프로 못 찾는
        # 유령 데이터(검색 불가한 개인정보)가 쌓이므로, 조용히 넘기지 말고 강하게 실패시켜
        # 설정 오류를 드러낸다. (scope_metadata_field는 write 키이자 read 필터 키다.)
        if not self._scope_field:
            logger.error(
                "scope_metadata_field 미설정 — elder 저장을 거부합니다. trace_id=%s session_id=%s",
                request.trace_id,
                request.session_id,
            )
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            context.set_details("scope_metadata_field 미설정으로 elder 저장을 할 수 없습니다.")
            return rag_pb2.StoreConversationResponse(stored_count=0)

        ids, texts, metadatas = self._prepare_elder_documents(request)
        if not ids:
            return rag_pb2.StoreConversationResponse(stored_count=0)

        try:
            embeddings = self._embedding.embed_documents(texts)
            self._repository.add_documents(
                ChromaCollection.ELDER, ids, embeddings, texts, metadatas
            )
        except Exception:
            logger.exception(
                "StoreConversation 저장 실패 trace_id=%s session_id=%s",
                request.trace_id,
                request.session_id,
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("elder 대화 저장에 실패했습니다.")
            return rag_pb2.StoreConversationResponse(stored_count=0)

        return rag_pb2.StoreConversationResponse(stored_count=len(ids))

    def _prepare_elder_documents(
        self, request: rag_pb2.StoreConversationRequest
    ) -> tuple[list[str], list[str], list[dict]]:
        """턴(STT텍스트+LLM응답)을 저장할 (ids, texts, metadatas)로 펼친다.

        id는 결정적(session:turn:role)이라 재호출 시 upsert로 멱등하다. 빈 텍스트는 건너뛴다.
        메타데이터는 read 스코프와 동일 키(scope_field)로 target_user_id를 부착하고, 삭제
        정책 기준이 되는 timestamp도 함께 붙인다(memory-state).
        """
        stored_at = datetime.now(timezone.utc).isoformat()
        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[dict] = []
        for turn in request.turns:
            for role, text in (("user", turn.stt_text), ("ai", turn.llm_response_text)):
                if not text.strip():
                    continue
                ids.append(f"{request.session_id}:{turn.turn_id}:{role}")
                texts.append(text)
                metadatas.append(
                    {
                        self._scope_field: request.target_user_id,
                        "session_id": request.session_id,
                        "turn_id": turn.turn_id,
                        "role": role,
                        "timestamp": stored_at,
                    }
                )
        return ids, texts, metadatas


def _to_proto_chunk(hit: SearchHit) -> rag_pb2.ContextChunk:
    return rag_pb2.ContextChunk(
        collection=hit.collection.value,
        document_id=hit.document_id,
        text=hit.text,
        score=hit.score,
    )


def _build_static_sparse_indexes(
    repository: ChromaRepository, tokenizer: KiwiTokenizer
) -> dict[ChromaCollection, SparseIndexProtocol]:
    """static_knowledge의 공유 BM25 색인을 기동 시 1회 구축한다(내용어 화이트리스트).

    elder는 요청별로 짓기 때문에 여기서 만들지 않는다. guardian은 검색 대상 아님.
    """
    collection = ChromaCollection.STATIC_KNOWLEDGE
    index = Bm25Index(tokenizer.tokenize)
    index.build(repository.load_documents(collection))
    logger.info("BM25 공유 색인 구축 완료: %s", collection.value)
    return {collection: index}


def _build_servicer(settings: Settings, repository: ChromaRepository) -> RagServicer:
    tokenizer = KiwiTokenizer()
    return RagServicer(
        embedding_client=EmbeddingClient(settings.embedding_model_name),
        repository=repository,
        context_builder=ContextBuilder(),
        top_k=settings.search_top_k,
        scope_metadata_field=settings.scope_metadata_field,
        tokenizer=tokenizer,
        static_sparse_indexes=_build_static_sparse_indexes(repository, tokenizer),
    )


def serve() -> None:
    """Start the RAG gRPC server."""
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    chroma_client = create_chroma_client(settings)
    wait_for_chroma(chroma_client, settings.chroma_connect_timeout_seconds)
    repository = ChromaRepository(chroma_client, rrf_k=settings.rrf_k)
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
