from dataclasses import dataclass

from wilson_rag.chroma_collections import ChromaCollection


@dataclass(frozen=True)
class RagContextRequest:
    query_text: str
    target_user_id: str
    session_id: str
    collections: tuple[ChromaCollection, ...]


@dataclass(frozen=True)
class RagContextChunk:
    collection: ChromaCollection
    document_id: str
    text: str
    score: float


class ContextBuilder:
    def build_fallback(self) -> list[RagContextChunk]:
        return []
