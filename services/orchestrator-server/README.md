# Orchestrator 서버 (③)

역할:

- Spring Boot 백엔드가 호출하는 **유일한 외부 gRPC 진입점**(`DialogueService.Converse`)
- STT → RAG → LLM → TTS 순서 조율
- STT 완료 후 치매/음성/감정 분석을 비동기로 트리거하고 MQ로 publish

이 서버는 수신용 REST router를 만들지 않는다(헬스체크 제외, grpc.md).

## 현재 범위 — Phase 1 텍스트 스파인 (#19)

음성(STT/TTS) 없이 **텍스트만으로** 전 구간(③→①→②)을 잇는다.

```
BE → Converse(AudioRequest) → [STT 브리지] → RAG BuildContext → LLM Generate(스트림)
                            → StreamResponse: MetadataFrame → CompletionFrame
```

- **STT 브리지(임시)**: Phase 1은 실제 STT를 붙이지 않는다. `AudioRequest.audio_payload`(bytes)를
  **UTF-8 텍스트로 해석**해 `stt_text`로 쓴다. Phase 2에서 이 자리에 Azure STT를 끼운다.
- **RAG 폴백**: `BuildContext` 실패는 대화를 끊지 않는다 — 빈 컨텍스트로 LLM을 진행한다(rag.md).
- **출력**: Phase 1은 TTS가 없어 `AudioChunk`를 흘리지 않는다. LLM 토큰 스트림은 내부적으로
  소비·누적해 `CompletionFrame.full_llm_response_text`로 1회 전달한다. Phase 2에서 이 토큰을
  TTS로 흘려 `AudioChunk`를 만든다.
- **실패 처리**: gRPC status로 스트림을 끊지 않고 `ErrorFrame`(STT/LLM 단계)을 흘린 뒤 정상 종료한다(grpc.md).

범위 밖(후속): 실제 STT/TTS 오디오 처리(Phase 2), 인지지표 Kafka publish(Phase 4),
응급 키워드 가드레일(RAG 측 TBD).

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `GRPC_HOST`/`GRPC_PORT` | `0.0.0.0`/`50051` | 외부 진입 gRPC 바인딩 |
| `RAG_SERVER_TARGET` | `localhost:50052` | RAG 유닛(①) gRPC 타깃. 클러스터는 `rag-server:50052` |
| `LLM_SERVER_TARGET` | `localhost:50053` | LLM 유닛(②) gRPC 타깃. 클러스터는 `llm-server:50053` |
| `LANGUAGE_CODE` | `ko-KR` | 대화 언어 |
| `SYSTEM_PROMPT` | (윌슨 기본 페르소나) | LLM 시스템 프롬프트. 비판단·비교정 원칙 반영 |

## 실행

```powershell
# 1) proto 스텁 생성(최초 1회 / proto 변경 시) — dialogue+rag+llm 세 계약 모두 생성
pip install -r services/orchestrator-server/requirements-dev.txt
python services/orchestrator-server/scripts/gen_proto.py

# 2) 런타임 의존성
pip install -r services/orchestrator-server/requirements.txt

# 3) 실행 (RAG=50052 / LLM=50053 가 떠 있어야 실제 대화가 동작)
$env:PYTHONPATH="services/orchestrator-server/src"
python -m wilson_orchestrator.main
```

## 배선 스모크 (외부 의존성 불필요)

가짜 RAG/LLM을 주입해 servicer→pipeline→프레임 조립을 왕복 검증한다(키·네트워크 불필요):

```powershell
$env:PYTHONPATH="services/orchestrator-server/src"
python services/orchestrator-server/scripts/smoke_spine.py
```
→ `frames : ['metadata', 'completion']` 와 `OK` 가 출력되면 배선 성공.

> 실제 RAG+LLM 연동 라이브 확인은 두 유닛(+ ChromaDB, NVIDIA 키)을 띄운 뒤
> `RAG_SERVER_TARGET`/`LLM_SERVER_TARGET`을 맞추고 위 `main`을 실행해 BE 클라이언트로 호출한다.
