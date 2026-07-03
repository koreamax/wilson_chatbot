class RagClient:
    async def build_context(self, query_text: str, target_user_id: str, session_id: str):
        raise NotImplementedError("RAG 서버 gRPC client 연결 필요")
