from typing import Protocol

from wilson_rag.chroma_collections import (
    COLLECTION_DESCRIPTIONS,
    ChromaCollection,
    REQUIRED_COLLECTIONS,
)


class ChromaClientProtocol(Protocol):
    def get_or_create_collection(self, name: str, metadata: dict | None = None): ...
    def list_collections(self): ...


class ChromaRepository:
    def __init__(self, client: ChromaClientProtocol) -> None:
        self.client = client

    def ensure_required_collections(self) -> None:
        for collection in REQUIRED_COLLECTIONS:
            self.client.get_or_create_collection(
                name=collection.value,
                metadata={
                    "display_name": COLLECTION_DESCRIPTIONS[collection],
                    "owner": "wilson-ai",
                },
            )

    def collection_names(self) -> list[str]:
        names: list[str] = []
        for collection in self.client.list_collections():
            if isinstance(collection, str):
                names.append(collection)
            else:
                names.append(collection.name)
        return names

    def has_required_collections(self) -> bool:
        existing = set(self.collection_names())
        required = {collection.value for collection in REQUIRED_COLLECTIONS}
        return required.issubset(existing)

    def collection_name(self, collection: ChromaCollection) -> str:
        return collection.value
