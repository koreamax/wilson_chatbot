class VectorRepository:
    def search(self, query_embedding):
        # 나중에 ChromaDB 검색 코드로 교체
        return [
            {
                "content": "검색된 문서 내용 예시",
                "score": 0.95
            }
        ]
