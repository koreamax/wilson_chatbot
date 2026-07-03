# ChromaDB 배포

ChromaDB는 상태를 가진 별도 배포 단위다.

- StatefulSet + PVC로 배포한다.
- 기본 배포는 클러스터 내부 접근용이다.
- 컬렉션 초기화 Job이 `static_knowledge`, `elder`, `guardian` 3개를 보장한다.

## 배포

### 로컬 Docker로 실행

AWS를 쓰지 않고 내 PC Docker에서 ChromaDB만 띄울 수 있다.

```powershell
docker compose -f services/chroma-db/docker-compose.yml up -d
```

내 PC에서 확인:

```text
http://localhost:8000
```

### 터널로 외부에 공유

사설 IP가 바뀌거나 같은 와이파이가 아니어도 접속하게 하려면 Cloudflare Quick Tunnel을 같이 띄운다.

```powershell
docker compose -f services/chroma-db/docker-compose.yml --profile tunnel up -d
```

터널 URL 확인:

```powershell
docker compose -f services/chroma-db/docker-compose.yml logs chroma-tunnel
```

로그에서 다음처럼 생긴 주소를 찾는다.

```text
https://example-random-name.trycloudflare.com
```

상대방 로컬 RAG 서버 환경변수:

```env
CHROMA_HOST=example-random-name.trycloudflare.com
CHROMA_PORT=443
CHROMA_SSL=true
```

`CHROMA_HOST`에는 `https://`를 빼고 hostname만 넣는다.

> Quick Tunnel 주소는 고정 주소가 아니다. 컨테이너를 다시 만들거나 터널이 재시작되면 주소가 바뀔 수 있다. 고정 주소가 필요하면 Cloudflare 계정과 도메인을 연결한 named tunnel이 필요하다.

### 같은 네트워크에서 공유

같은 와이파이/내부망의 팀원이 접속:

```text
http://<내-PC-사설-IP>:8000
```

상대방 로컬 RAG 서버 환경변수:

```env
CHROMA_HOST=<내-PC-IP>
CHROMA_PORT=8000
CHROMA_SSL=false
```

컨테이너 상태 확인:

```powershell
docker compose -f services/chroma-db/docker-compose.yml ps
docker compose -f services/chroma-db/docker-compose.yml logs chroma-init
```

중지:

```powershell
docker compose -f services/chroma-db/docker-compose.yml down
```

데이터까지 삭제:

```powershell
docker compose -f services/chroma-db/docker-compose.yml down -v
```

> 공용 인터넷에서 접속시키려면 공유기 포트포워딩, 방화벽 인바운드 허용, 또는 무료 터널이 필요하다. ChromaDB는 현재 인증 없이 열리므로 실제 개인정보나 대화 데이터는 넣지 않는다.

### Kubernetes로 실행

```powershell
kubectl apply -k services/chroma-db/k8s/base
```

클러스터 내부 주소:

```text
chroma-db:8000
```

데이터는 PVC `chroma-data`에 저장된다.

## 다른 사람이 로컬 RAG 서버에서 접속하는 방법

### 방법 1: NodePort로 열기

추가 LoadBalancer 비용 없이 열려면 NodePort overlay를 적용한다.

```powershell
kubectl apply -k services/chroma-db/k8s/overlays/nodeport
```

접속 주소:

```text
http://<node-ip>:30800
```

이 방식은 별도 AWS LoadBalancer 비용이 들지 않는다. 다만 다음 조건이 필요하다.

- EKS 워커 노드가 public IP를 가져야 한다.
- 워커 노드 보안그룹 inbound에 TCP `30800`이 열려 있어야 한다.
- 상대방이 `http://<node-ip>:30800`에 접근 가능한 네트워크여야 한다.

노드 IP 확인:

```powershell
kubectl get nodes -o wide
```

Docker Desktop Kubernetes라면 보통 다음 주소로도 확인할 수 있다.

```text
http://localhost:30800
```

로컬 RAG 서버 환경변수 예시:

```env
CHROMA_HOST=<node-ip>
CHROMA_PORT=30800
CHROMA_SSL=false
```

### 방법 2: port-forward로 임시 공유

개발자가 본인 PC에서만 잠깐 열어줄 때 사용한다.

```powershell
kubectl port-forward statefulset/chroma-db 8000:8000 --address 0.0.0.0
```

같은 네트워크의 팀원은 다음 주소로 접속한다.

```text
http://<port-forward를 실행한 PC의 IP>:8000
```

로컬 RAG 서버 환경변수 예시:

```env
CHROMA_HOST=<port-forward를 실행한 PC의 IP>
CHROMA_PORT=8000
CHROMA_SSL=false
```

> ChromaDB는 현재 인증 없이 열리는 개발용 설정이다. 공용 인터넷에 열 경우 누구나 읽기/쓰기/삭제가 가능하므로 실제 개인정보나 대화 데이터는 넣지 않는다.

## 컬렉션 확인

초기화 Job 로그:

```powershell
kubectl logs job/chroma-db-init-collections
```

초기화 Job을 다시 실행해야 하면 기존 Job을 지우고 다시 apply한다.

```powershell
kubectl delete job chroma-db-init-collections
kubectl apply -k services/chroma-db/k8s/base
```

Pod 상태:

```powershell
kubectl get pod,svc,pvc | findstr chroma
```
