from collections.abc import Callable

from rank_bm25 import BM25Okapi


class Bm25Index:
    """문서 집합에 대한 인메모리 BM25 색인.

    ChromaDB 로컬 모드는 sparse 색인을 지원하지 않으므로 dense와 **물리적으로 분리**해
    운용한다(rag.md). static_knowledge는 기동 시 1회 구축·상주하고, elder는 그 노인 문서로만
    요청별로 짧게 구축·폐기한다. 토큰화 함수를 주입받아 static(전체 토큰)/elder(명사만) 등
    용도별로 다른 토큰화를 쓸 수 있다. 토크나이저를 직접 import하지 않고 주입받아 가볍다.
    """

    def __init__(self, tokenize: Callable[[str], list[str]]) -> None:
        self._tokenize = tokenize
        self._doc_ids: list[str] = []
        self._texts: list[str] = []
        self._bm25: BM25Okapi | None = None

    def build(self, documents: list[tuple[str, str]]) -> None:
        """(document_id, text) 목록으로 색인을 구축한다."""
        self._doc_ids = [doc_id for doc_id, _ in documents]
        self._texts = [text for _, text in documents]
        corpus = [self._tokenize(text) for text in self._texts]
        # 토큰이 하나도 없으면(빈 코퍼스/전부 필터됨) BM25Okapi가 0으로 나눠 실패하므로 None.
        if not any(corpus):
            self._bm25 = None
        else:
            self._bm25 = BM25Okapi(corpus)

    def is_empty(self) -> bool:
        return self._bm25 is None

    def search(self, query_text: str, top_k: int) -> list[tuple[str, str]]:
        """BM25 점수 상위 top_k를 (document_id, text) 순위대로 반환한다.

        점수 0(용어 미일치) 문서는 제외한다 — RRF에 잡음 순위로 끼지 않게 한다.
        """
        if self._bm25 is None:
            return []
        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        ranked = [
            index
            for index in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            if scores[index] > 0
        ][:top_k]
        return [(self._doc_ids[index], self._texts[index]) for index in ranked]
