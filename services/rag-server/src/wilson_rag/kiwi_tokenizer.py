from kiwipiepy import Kiwi

# BM25 색인 대상 내용어 품사 화이트리스트(rag.md): 일반명사·고유명사·외국어·숫자·한자.
# 조사·어미 등 기능어는 색인 가치가 없어 제외한다.
_CONTENT_TAGS = frozenset({"NNG", "NNP", "SL", "SN", "SH"})
# 파생·전성 명사 병합의 선두 품사(명사+파생접미사 XSN 패턴).
_MERGE_NOUN_HEADS = frozenset({"NNG", "NNP"})


class KiwiTokenizer:
    """한국어 형태소 토크나이저 (kiwipiepy). BM25 토큰화용.

    rag.md: cognitive-metrics와 **공용 인스턴스 원칙**이라, 같은 토크나이저를 치매탐지
    형태소 분석에서도 재사용할 수 있게 이 모듈로 분리한다(현재는 BM25만 사용).
    색인·질의 양쪽에 동일한 토큰화·필터를 적용한다.
    """

    def __init__(self) -> None:
        self._kiwi = Kiwi()

    def add_user_word(self, word: str, tag: str = "NNP") -> None:
        """런타임 사용자사전 등록(고유명사 파편화 방지). 무중단으로 이름·지명을 단일 NNP로."""
        self._kiwi.add_user_word(word, tag)

    def tokenize(self, text: str) -> list[str]:
        """내용어 화이트리스트 토큰(표면형)을 돌려준다.

        파생·전성 명사가 화이트리스트 필터로 유실되지 않도록 후처리 병합을 적용한다:
        어간(VV)+전성어미(ETN), 명사(NNG/NNP)+파생접미사(XSN) 패턴을 **원문 표면형**으로
        단일 명사로 복원한다(예: "알림", "할인권"이 증발하지 않게).
        """
        tokens = self._kiwi.tokenize(text)
        result: list[str] = []
        i = 0
        n = len(tokens)
        while i < n:
            current = tokens[i]
            if i + 1 < n:
                nxt = tokens[i + 1]
                is_vv_etn = current.tag.startswith("VV") and nxt.tag == "ETN"
                is_noun_xsn = current.tag in _MERGE_NOUN_HEADS and nxt.tag == "XSN"
                if is_vv_etn or is_noun_xsn:
                    # 원문 span으로 표면형 복원(자소 분해로 form을 이어붙일 수 없으므로).
                    result.append(text[current.start : nxt.start + nxt.len])
                    i += 2
                    continue
            if current.tag in _CONTENT_TAGS:
                result.append(current.form)
            i += 1
        return result
