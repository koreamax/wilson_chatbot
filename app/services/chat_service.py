from app.services.rag_service import RagService


class ChatService:
    def __init__(self):
        self.rag_service = RagService()

    def chat(self, message: str):
        result = self.rag_service.search(message)

        return {
            "question": message,
            "answer": "아직 LLM 연결 전입니다.",
            "retrieved_context": result
        }
