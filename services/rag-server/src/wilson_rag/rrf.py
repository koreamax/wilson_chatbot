def reciprocal_rank_fusion(rankings: list[list[str]], k: int) -> dict[str, float]:
    """여러 순위 리스트를 RRF로 융합한다.

    각 ranking은 doc_id를 순위(상위→하위)대로 담은 리스트다. 스케일이 다른 원점수를
    합산하지 않고 **순위만** 사용한다(rag.md). score = Σ 1/(k + rank), rank는 1부터.
    반환은 {doc_id: rrf_score} (정렬은 호출측 책임).
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores
