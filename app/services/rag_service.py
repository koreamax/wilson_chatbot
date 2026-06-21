from app.services.embedding_service import EmbeddingService
from app.repositories.vector_repository import VectorRepository


class RagService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_repository = VectorRepository()

    def search(self, query: str):
        query_embedding = self.embedding_service.embed(query)
        return self.vector_repository.search(query_embedding)

    def upload_document(self):
        return {
            "message": "문서 업로드 기능은 아직 구현 전입니다."
        }
