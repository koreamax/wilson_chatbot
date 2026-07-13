from enum import StrEnum


class ChromaCollection(StrEnum):
    STATIC_KNOWLEDGE = "static_knowledge"
    ELDER = "elder"
    GUARDIAN = "guardian"


COLLECTION_DESCRIPTIONS: dict[ChromaCollection, str] = {
    ChromaCollection.STATIC_KNOWLEDGE: "정적 지식",
    ChromaCollection.ELDER: "노인 개인 컨텍스트",
    ChromaCollection.GUARDIAN: "보호자 컨텍스트",
}

REQUIRED_COLLECTIONS: tuple[ChromaCollection, ...] = tuple(ChromaCollection)

# rag.md 절대 규칙: 컬렉션은 반드시 cosine 거리 지표로 생성한다.
# KURE-v1 임베딩이 코사인 유사도로 훈련됐고, ChromaDB 기본값(L2)을 쓰면 검색 품질이 훼손된다.
# 설정 노브가 아니라 불변 규칙이므로 상수로 둔다.
HNSW_SPACE: str = "cosine"
