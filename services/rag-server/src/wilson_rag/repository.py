import logging
from dataclasses import dataclass
from typing import Any, Protocol

from wilson_rag.chroma_collections import (
    COLLECTION_DESCRIPTIONS,
    ChromaCollection,
    HNSW_SPACE,
    REQUIRED_COLLECTIONS,
)
from wilson_rag.rrf import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    """단일 컬렉션 검색 결과 1건(내부 표현)."""

    collection: ChromaCollection
    document_id: str
    text: str
    # 융합 점수(하이브리드는 RRF, sparse 색인이 없으면 dense 단독 = 1 - cosine distance).
    score: float


class ChromaClientProtocol(Protocol):
    def get_or_create_collection(
        self,
        name: str,
        metadata: dict | None = None,
        configuration: dict | None = None,
        embedding_function: Any = None,
    ): ...
    def get_collection(self, name: str, embedding_function: Any = None): ...
    def list_collections(self): ...


class SparseIndexProtocol(Protocol):
    """BM25 색인 덕타이핑. 실물(Bm25Index)은 fugashi를 끌어오므로 여기서 import하지 않는다
    (healthcheck·init_collections가 repository만 import해도 fugashi가 필요해지지 않게)."""

    def search(self, query_text: str, top_k: int) -> list[tuple[str, str]]: ...
    def is_empty(self) -> bool: ...


class ChromaRepository:
    def __init__(self, client: ChromaClientProtocol, rrf_k: int = 60) -> None:
        self.client = client
        self._rrf_k = rrf_k

    def load_documents(
        self, collection: ChromaCollection, where: dict | None = None
    ) -> list[tuple[str, str]]:
        """컬렉션의 (document_id, text)를 읽어온다(BM25 색인 구축용).

        `where`로 스코프를 걸 수 있다. static_knowledge는 where=None(전량), elder는
        where={target_user_id}로 그 노인 문서만 읽어 요청별 스코프 BM25를 짓는다.
        """
        chroma_collection = self.client.get_collection(
            collection.value, embedding_function=None
        )
        got = chroma_collection.get(where=where, include=["documents"])
        return [(doc_id, text or "") for doc_id, text in zip(got["ids"], got["documents"])]

    def add_documents(
        self,
        collection: ChromaCollection,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """컬렉션에 문서를 upsert한다(elder write). 결정적 id로 멱등하게 재호출 가능."""
        chroma_collection = self.client.get_collection(
            collection.value, embedding_function=None
        )
        chroma_collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def ensure_required_collections(self) -> None:
        for collection in REQUIRED_COLLECTIONS:
            created = self.client.get_or_create_collection(
                name=collection.value,
                metadata={
                    "display_name": COLLECTION_DESCRIPTIONS[collection],
                    "owner": "wilson-ai",
                },
                # rag.md 절대 규칙: cosine 거리 지표 강제. 생성이 중앙화된 이곳에서 강제해
                # 서버 기동·초기화 Job 등 모든 생성 경로가 cosine을 보장하게 한다.
                configuration={"hnsw": {"space": HNSW_SPACE}},
                # 임베딩은 ruri-v3가 담당하고 벡터를 명시 전달한다. 기본 EF를 넘기면
                # cosine 유효성 검증을 위해 ONNX 기본 모델을 내려받으므로 None으로 둔다.
                embedding_function=None,
            )
            self._assert_cosine(collection, created)

    def _assert_cosine(self, collection: ChromaCollection, created: Any) -> None:
        """생성된 컬렉션의 거리 지표가 cosine인지 되읽어 검증한다.

        get_or_create_collection은 컬렉션이 이미 존재하면 configuration을 무시하므로,
        과거에 L2로 만들어진 볼륨은 자동 교정되지 않는다. 되읽기 검증이 그런 잘못된
        컬렉션을 잡아내는 유일한 안전장치다. cosine이 아니면 강하게 실패한다.
        """
        # ASSUMPTION: chromadb 1.5.9에서 configuration_json 형태는
        # {"hnsw": {"space": "cosine"|"l2", ...}, "spann": ..., ...} (실물 되읽기로 확인).
        try:
            actual_space = created.configuration_json["hnsw"]["space"]
        except (AttributeError, KeyError, TypeError) as exc:
            logger.error(
                "컬렉션 '%s'의 거리 지표를 되읽지 못했습니다. cosine 강제를 검증할 수 없습니다.",
                collection.value,
            )
            raise RuntimeError(
                f"컬렉션 '{collection.value}'의 hnsw.space를 확인할 수 없습니다. "
                f"cosine 강제 검증 실패."
            ) from exc

        if actual_space != HNSW_SPACE:
            logger.error(
                "컬렉션 '%s'의 거리 지표가 '%s'입니다(기대: '%s'). "
                "과거 L2로 생성된 컬렉션은 자동 교정되지 않습니다.",
                collection.value,
                actual_space,
                HNSW_SPACE,
            )
            raise RuntimeError(
                f"컬렉션 '{collection.value}'가 '{actual_space}' 거리 지표로 존재합니다"
                f"(기대: '{HNSW_SPACE}'). 해당 컬렉션을 삭제 후 재생성하거나 "
                f"ChromaDB 볼륨을 리셋하십시오."
            )

    def dense_search(
        self,
        collection: ChromaCollection,
        query_embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[SearchHit]:
        """단일 컬렉션에 대해 dense(cosine) 검색을 수행한다.

        private 컬렉션(elder/guardian)은 반드시 `where` 스코프 필터와 함께 호출한다.
        스코프 없는 private 검색은 개인정보 유출이므로 이 판단은 호출측(servicer)이 진다.
        임베딩은 명시 전달하므로 컬렉션 EF는 사용하지 않는다(embedding_function=None).
        """
        chroma_collection = self.client.get_collection(
            collection.value, embedding_function=None
        )
        result = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "distances"],
        )
        # chromadb는 배치 쿼리 형태로 반환한다 — 단일 쿼리이므로 [0]을 꺼낸다.
        ids = result["ids"][0]
        documents = result["documents"][0]
        distances = result["distances"][0]

        hits: list[SearchHit] = []
        for document_id, text, distance in zip(ids, documents, distances):
            hits.append(
                SearchHit(
                    collection=collection,
                    document_id=document_id,
                    text=text or "",
                    # cosine space: distance ∈ [0,2], 유사도 = 1 - distance.
                    # dense 단독 잠정 점수다. 4단계 RRF 융합 시 이 값을 대체한다.
                    score=1.0 - distance,
                )
            )
        return hits

    def hybrid_search(
        self,
        collection: ChromaCollection,
        query_text: str,
        query_embedding: list[float],
        top_k: int,
        where: dict | None = None,
        sparse_index: SparseIndexProtocol | None = None,
    ) -> list[SearchHit]:
        """dense + BM25(sparse)를 RRF로 융합해 반환한다.

        sparse_index는 호출측(servicer)이 주입한다 — public은 기동 시 만든 공유 정적 색인,
        elder는 그 노인 문서로만 요청별로 빌드한 스코프 색인이다. 후자는 스코프된 문서로만
        지어지므로 유출이 구조적으로 불가능하다(dense의 where 스코프와 정합). sparse_index가
        없으면 dense 단독으로 정상 degrade한다. 결합은 순위 기반 RRF로만 한다(rag.md).
        """
        dense_hits = self.dense_search(collection, query_embedding, top_k, where=where)

        if sparse_index is None or sparse_index.is_empty():
            return dense_hits

        sparse_results = sparse_index.search(query_text, top_k)

        # 두 결과의 doc_id→text 매핑(어느 쪽에서 나온 문서든 텍스트를 복원할 수 있게).
        text_by_id: dict[str, str] = {hit.document_id: hit.text for hit in dense_hits}
        for doc_id, text in sparse_results:
            text_by_id.setdefault(doc_id, text)

        dense_ranking = [hit.document_id for hit in dense_hits]
        sparse_ranking = [doc_id for doc_id, _ in sparse_results]
        fused = reciprocal_rank_fusion([dense_ranking, sparse_ranking], self._rrf_k)

        ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            SearchHit(
                collection=collection,
                document_id=doc_id,
                text=text_by_id.get(doc_id, ""),
                score=score,
            )
            for doc_id, score in ordered
        ]

    def collection_names(self) -> list[str]:
        names: list[str] = []
        for collection in self.client.list_collections():
            if isinstance(collection, str):
                names.append(collection)
            else:
                names.append(collection.name)
        return names

    def has_required_collections(self) -> bool:
        existing = set(self.collection_names())
        required = {collection.value for collection in REQUIRED_COLLECTIONS}
        return required.issubset(existing)

    def collection_name(self, collection: ChromaCollection) -> str:
        return collection.value
