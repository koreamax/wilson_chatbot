import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# KURE-v1(nlpai-lab/KURE-v1)은 쿼리·문서 어느 쪽에도 프리픽스/지시어를 요구하지 않는다.
# 원문 텍스트를 그대로 인코딩한다. (일본어판 ruri가 강제하던 검색쿼리/검색문서 프리픽스를
# 붙이면 KURE에서는 오히려 검색 품질이 저하되므로 붙이지 않는다 — rag.md.)
# read(query)와 write(document)가 같은 모델·차원(1024)·정규화를 공유해야 검색이 유의미하다.


class EmbeddingClient:
    """KURE-v1 로컬 임베딩. 외부 임베딩 API를 쓰지 않는다(rag.md: PII/PHI).

    모델 로드는 무겁고 최초 1회면 되므로 지연 로딩 후 재사용한다. KURE-v1은 L2 정규화된
    1024차원 단위 벡터를 반환하므로 cosine 거리와 정합한다.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _model_or_load(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("임베딩 모델 로드 시작: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info("임베딩 모델 로드 완료: %s", self._model_name)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        """검색 쿼리 1건을 임베딩한다(프리픽스 없이 원문 그대로)."""
        model = self._model_or_load()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """저장할 문서 여러 건을 배치로 임베딩한다(프리픽스 없이 원문 그대로).

        세션 종료 후 write에서 사용한다. read(embed_query)와 동일 모델·차원·정규화를 쓴다.
        """
        if not texts:
            return []
        model = self._model_or_load()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]
