import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(name="test_collection")

collection.upsert(
    ids=["1", "2"],
    documents=[
        "FastAPI는 Python 웹 프레임워크이다.",
        "ChromaDB는 RAG에서 벡터 검색에 사용된다."
    ]
)

results = collection.query(
    query_texts=["RAG 벡터 검색"],
    n_results=1
)

print(results)
