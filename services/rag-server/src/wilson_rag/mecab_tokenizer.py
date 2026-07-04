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

        # ASSUMPTION: 표층형으로 토큰화한다. 기본형(lemma) 정규화는 후순위.
        """
        return [word.surface for word in self._tagger(text) if word.surface.strip()]

    def tokenize_nouns(self, text: str) -> list[str]:
        """명사(名詞) 표층형만 돌려준다 — 고유명사 중심 경량 색인용(elder BM25).

        조사·조동사 등 잡음을 버려 색인을 경량화하고 dense와 역할을 직교시킨다(의미=dense,
        식별자(사람·지명·약명)=sparse). 固有名詞도 pos1 상 名詞라 함께 포착된다.
        """
        return [
            word.surface
            for word in self._tagger(text)
            if word.surface.strip() and getattr(word.feature, "pos1", None) == "名詞"
        ]
