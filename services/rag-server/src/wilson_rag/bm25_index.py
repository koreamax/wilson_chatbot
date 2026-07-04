from rank_bm25 import BM25Okapi

from wilson_rag.mecab_tokenizer import MeCabTokenizer


class Bm25Index:
    """단일 컬렉션 문서에 대한 인메모리 BM25 색인.

    ChromaDB 로컬 모드는 sparse 색인을 지원하지 않으므로 dense와 **물리적으로 분리**해
    운용한다(rag.md). 기동 시 1회 구축·상주하며, 주기적 리프레시(TTL)는 후순위 확장이다.
    """

    def __init__(self, tokenizer: MeCabTokenizer) -> None:
        self._tokenizer = tokenizer
        self._doc_ids: list[str] = []
        self._texts: list[str] = []
        self._bm25: BM25Okapi | None = None

    def build(self, documents: list[tuple[str, str]]) -> None:
        """(document_id, text) 목록으로 색인을 구축한다."""
        self._doc_ids = [doc_id for doc_id, _ in documents]
        self._texts = [text for _, text in documents]
        corpus = [self._tokenizer.tokenize(text) for text in self._texts]
        # 문서가 없으면 BM25Okapi가 빈 코퍼스에서 실패할 수 있으므로 None으로 둔다.
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def is_empty(self) -> bool:
        return self._bm25 is None

    def search(self, query_text: str, top_k: int) -> list[tuple[str, str]]:
        """BM25 점수 상위 top_k를 (document_id, text) 순위대로 반환한다.

        점수 0(용어 미일치) 문서는 제외한다 — RRF에 잡음 순위로 끼지 않게 한다.
        """
        if self._bm25 is None:
            return []
        query_tokens = self._tokenizer.tokenize(query_text)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        ranked = [
            index
            for index in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            if scores[index] > 0
        ][:top_k]
        return [(self._doc_ids[index], self._texts[index]) for index in ranked]
