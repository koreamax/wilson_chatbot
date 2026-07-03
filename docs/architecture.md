# Wilson AI 아키텍처 메모

이 문서는 ERD가 확정되기 전에도 흔들리지 않을 구조 결정을 기록한다. 앞으로 작업할 때 이 문서를 기준으로 삼는다.

## 확정한 배포 단위

| 디렉터리 | 배포 단위 | 역할 | 상태 |
|---|---|---|---|
| `services/rag-server` | RAG 서버 | 임베딩, Chroma 검색, 컨텍스트 조립 | stateless |
| `services/ollama-gpt-server` | Ollama GPT 서버 | LLM 추론, 토큰 스트리밍 | stateless |
| `services/orchestrator-server` | STT·TTS·치매탐지 + 오케스트레이션 서버 | BE가 호출하는 gRPC 진입점, STT→RAG→LLM→TTS 조율, 분석 MQ publish | stateless |
| `services/chroma-db` | ChromaDB | 벡터 저장·검색 | stateful |

## gRPC 원칙

- 외부 inbound 비즈니스 요청은 gRPC만 허용한다.
- FastAPI `router` 구조는 사용하지 않는다.
- BE → AI 진입점은 `orchestrator-server`의 `DialogueService.Converse`다.
- `Converse`는 unary 입력 + server streaming 출력이다.
- 스트림 첫 프레임은 `MetadataFrame`, 정상 종료는 `CompletionFrame`, 실패 종료는 `ErrorFrame`이다.
- 스트리밍 중 애플리케이션 오류를 gRPC status로 끊지 않고 `ErrorFrame` 후 정상 종료한다.
- AI 내부 MSA 간 통신 규격은 `proto/wilson/rag/v1`과 `proto/wilson/llm/v1`에서 별도로 관리한다.

## Chroma 컬렉션

ERD 확정 전에도 컬렉션 경계는 다음 3개로 고정한다.

| 컬렉션 | 의미 | 주의 |
|---|---|---|
| `static_knowledge` | 일반 치매 케어, 서비스 공통 지식 | 개인 식별정보 저장 금지 |
| `elder` | 노인 개인 대화·요약 컨텍스트 | 노인 스코프 필터 필수 |
| `guardian` | 보호자 대화·돌봄 컨텍스트 | 보호자 스코프 필터 필수 |

`subject_id`, `guardian_id`, `session_id`, `turn_id`의 DB 관계와 삭제 규칙은 ERD 확정 뒤 repository 어댑터에 반영한다.

## ERD 전까지 하지 않을 일

- PostgreSQL 테이블 구조 가정
- conversation/session/document id 규칙 확정
- private 벡터 삭제 범위 확정
- 보호자-노인 권한 관계를 AI 서버에서 직접 판단
- 수신용 REST API 추가

## ERD 전에도 가능한 일

- `.proto` 계약 정리
- 4개 서비스별 Docker/Kubernetes 배포 경계 정리
- Ollama/RAG/Chroma/STT/TTS 어댑터 인터페이스 작성
- Chroma 컬렉션 3개 생성·검증 로직 작성
- gRPC 스트림 프레임 순서 테스트
