import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ruri-v3 "1+3 프리픽스 스킴". 검색 쿼리에는 반드시 이 프리픽스를 붙인다.
# (문서 임베딩은 "検索文書: "를 쓰지만 그건 write측(memory-state) 책임이라 여기선 다루지 않는다.)
QUERY_PREFIX = "検索クエリ: "


class EmbeddingClient:
    """ruri-v3-310m 로컬 임베딩. 외부 임베딩 API를 쓰지 않는다(rag.md: PII/PHI).

    모델 로드는 무겁고(수백 MB) 최초 1회면 되므로 지연 로딩 후 재사용한다.
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
        """검색 쿼리 1건을 768차원 벡터로 임베딩한다(쿼리 프리픽스 적용)."""
        model = self._model_or_load()
        vector = model.encode(QUERY_PREFIX + text, normalize_embeddings=True)
        return vector.tolist()
