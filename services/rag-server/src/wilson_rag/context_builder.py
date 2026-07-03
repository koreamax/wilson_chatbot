from wilson_rag.repository import SearchHit


class ContextBuilder:
    """검색 결과(SearchHit) → 응답 컨텍스트 조립 + 폴백 처리.

    청킹 전략(Parent-Child / Sentence Window)은 후속 단계에서 반영한다.
    현재는 여러 컬렉션의 hit을 점수 내림차순으로 합쳐 반환하고, 결과가 비면 폴백으로 표시한다.
    """

    def assemble(self, hits: list[SearchHit]) -> tuple[list[SearchHit], bool]:
        """(정렬된 chunks, fallback_used)를 돌려준다.

        검색이 공백이면 빈 컨텍스트 + fallback_used=True. rag.md 폴백 규칙상 검색이
        비거나 실패해도 대화 루프는 유지한다(LLM이 일반 응답 생성).
        """
        if not hits:
            return [], True
        ordered = sorted(hits, key=lambda hit: hit.score, reverse=True)
        return ordered, False
