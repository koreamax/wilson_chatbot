# RAG 서버

역할:

- 질의/문서 임베딩
- ChromaDB 검색
- 검색 결과를 LLM에 넣기 좋은 컨텍스트로 조립

Chroma 컬렉션은 반드시 3개만 사용한다.

- `static_knowledge`
- `elder`
- `guardian`

이 서버는 DB ERD를 직접 가정하지 않는다. 사용자·세션 권한 필터는 BE가 검증한 식별자를 기준으로만 적용한다.

## ChromaDB 연결

Kubernetes 기본 연결 주소:

```text
CHROMA_HOST=chroma-db
CHROMA_PORT=8000
```

RAG 서버는 시작 시 ChromaDB에 연결한 뒤 필수 컬렉션 3개를 생성하거나 확인한다.

로컬에서 확인:

```powershell
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8000"
python -m wilson_rag.init_collections
```
