import fugashi


class MeCabTokenizer:
    """일본어 형태소 토크나이저 (fugashi + unidic-lite).

    rag.md: BM25 토큰화용. cognitive-metrics와 **공용 인스턴스 원칙**이라, 같은 토크나이저를
    치매탐지 형태소 분석에서도 재사용할 수 있게 이 모듈로 분리한다(현재는 BM25만 사용).
    unidic-lite 번들 사전을 쓰므로 시스템 MeCab 바이너리가 필요 없다.
    """

    def __init__(self) -> None:
        self._tagger = fugashi.Tagger()

    def tokenize(self, text: str) -> list[str]:
        """표층형(surface) 토큰 리스트를 돌려준다(공백 토큰 제외).

        # ASSUMPTION: MVP는 표층형으로 토큰화한다. 품사 필터·기본형(lemma) 정규화는
        # 검색 품질 고도화 시 도입(후순위). rag.md는 이 결과를 BM25 토큰으로만 해석한다.
        """
        return [word.surface for word in self._tagger(text) if word.surface.strip()]
