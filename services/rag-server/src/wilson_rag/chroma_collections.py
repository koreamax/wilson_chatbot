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
