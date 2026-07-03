# Wilson AI Monorepo

Wilson AI 서버는 하나의 레포 안에서 4개 배포 단위로 관리한다.

1. `services/rag-server`: 임베딩, Chroma 검색, 컨텍스트 조립
2. `services/ollama-gpt-server`: Ollama 기반 LLM 추론과 토큰 스트리밍
3. `services/orchestrator-server`: 외부 gRPC 진입점, STT → RAG → LLM → TTS 오케스트레이션, 치매/음성 분석 트리거
4. `services/chroma-db`: ChromaDB Stateful 배포

외부 비즈니스 요청은 REST 라우터가 아니라 gRPC로만 받는다. 헬스체크를 제외하고 FastAPI 라우터를 만들지 않는다.

현재 합의한 Chroma 컬렉션은 3개다.

- `static_knowledge`: 정적 지식
- `elder`: 노인 개인 컨텍스트
- `guardian`: 보호자 컨텍스트

자세한 구조와 결정 사항은 [docs/architecture.md](docs/architecture.md)를 본다.

## 폴더 구조

```text
proto/
  wilson/dialogue/v1/   # BE → AI 외부 gRPC 계약
  wilson/rag/v1/        # orchestrator → RAG 내부 계약
  wilson/llm/v1/        # orchestrator → LLM 내부 계약

services/
  orchestrator-server/  # gRPC 진입점, STT/RAG/LLM/TTS 조율
  rag-server/           # 임베딩, Chroma 검색, 컨텍스트 조립
  ollama-gpt-server/    # Ollama LLM 추론
  chroma-db/            # ChromaDB StatefulSet
```

## 서비스별 빌드

monorepo 루트에서 서비스별 Dockerfile을 지정해 빌드한다.

```powershell
docker build -f services/orchestrator-server/Dockerfile -t wilson/orchestrator-server:dev .
docker build -f services/rag-server/Dockerfile -t wilson/rag-server:dev .
docker build -f services/ollama-gpt-server/Dockerfile -t wilson/ollama-gpt-server:dev .
```

ChromaDB는 공식 이미지를 사용하므로 별도 빌드하지 않는다.

## 서비스별 배포

```powershell
kubectl apply -k services/chroma-db/k8s/base
kubectl apply -k services/rag-server/k8s/base
kubectl apply -k services/ollama-gpt-server/k8s/base
kubectl apply -k services/orchestrator-server/k8s/base
```

Spring Boot 백엔드는 `orchestrator-server:50051`만 호출한다. RAG, LLM, ChromaDB는 AI 내부 서비스다.

## ChromaDB만 먼저 배포하는 경우

RAG 서버를 다른 사람이 로컬에서 실행하고, 내 쪽에서는 ChromaDB만 띄울 수 있다.

### 비용 없이 내 Docker에서 띄우기

```powershell
docker compose -f services/chroma-db/docker-compose.yml up -d
```

외부 사람이 접속해야 하면 터널까지 같이 띄운다.

```powershell
docker compose -f services/chroma-db/docker-compose.yml --profile tunnel up -d
docker compose -f services/chroma-db/docker-compose.yml logs chroma-tunnel
```

로그에 나오는 `https://...trycloudflare.com` 주소를 상대방에게 공유한다.

상대방 RAG 서버 환경변수:

```env
CHROMA_HOST=<random>.trycloudflare.com
CHROMA_PORT=443
CHROMA_SSL=true
```

같은 네트워크에서만 접근한다면:

```env
CHROMA_HOST=<내-PC-IP>
CHROMA_PORT=8000
CHROMA_SSL=false
```

Quick Tunnel 주소는 재시작 시 바뀔 수 있다.

### Kubernetes에서 띄우기

클러스터 내부용:

```powershell
kubectl apply -k services/chroma-db/k8s/base
```

로컬 RAG 서버가 공용 인터넷에서 붙어야 하지만 비용을 추가로 내지 않으려면 NodePort overlay를 적용한다.

```powershell
kubectl apply -k services/chroma-db/k8s/overlays/nodeport
kubectl get svc chroma-db-nodeport
```

접속 주소:

```text
http://<node-ip>:30800
```

로컬 RAG 서버 환경변수 예시:

```env
CHROMA_HOST=<node-ip>
CHROMA_PORT=30800
CHROMA_SSL=false
```

이 방식은 AWS LoadBalancer를 만들지 않으므로 별도 LB 비용이 들지 않는다. 대신 워커 노드 public IP와 보안그룹 inbound TCP `30800` 허용이 필요하다.

컬렉션은 ChromaDB 초기화 Job이 자동으로 만든다.

```text
static_knowledge
elder
guardian
```

자세한 내용은 [services/chroma-db/README.md](services/chroma-db/README.md)를 본다.
