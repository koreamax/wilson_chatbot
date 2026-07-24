# Orchestrator 서버 (③)

역할:

- Spring Boot 백엔드가 호출하는 **유일한 외부 gRPC 진입점**(`DialogueService.Converse`)
- STT → RAG → LLM → TTS 순서 조율
- STT 완료 후 치매/음성/감정 분석을 비동기로 트리거하고 MQ로 publish

이 서버는 수신용 REST router를 만들지 않는다(헬스체크 제외, grpc.md).

## 현재 범위 — Phase 2 음성 파이프라인 (STT #22 · TTS #24)

음성 왕복 루프 완성 — 입력·출력 모두 **Azure Speech**(동일 리소스·키·리전 재사용).

```
BE → Converse(AudioRequest) → [Azure STT] → RAG BuildContext → LLM Generate(스트림)
                            → [Azure TTS(문장별)] → StreamResponse:
                               MetadataFrame → AudioChunk(seq)… → CompletionFrame
```

- **STT (Azure Speech)**: `audio_payload`를 short-audio REST로 전사(async). 리전 `koreacentral` 고정.
  원본 음성 인메모리 처리(디스크 기록 안 함). `audio_format`은 힌트로만 쓰고 **실제 바이트로 컨테이너 판별**
  (WAV/OGG-OPUS 지원, m4a 등은 후속). 대화용 `stt_text`=`DisplayText`, 인지지표용 `Lexical`은 `format=detailed`로 수신 가능.
- **RAG 폴백**: `BuildContext` 실패는 대화를 끊지 않는다 — 빈 컨텍스트로 LLM을 진행한다(rag.md).
- **TTS (Azure Speech)**: LLM 응답을 **문장 단위로 순차 합성**해 `AudioChunk(data, sequence)`로 스트리밍한다.
  전체 대기 후 일괄 전송하지 않는다(첫 음성 지연 단축). STT와 **동일 키·리전 재사용**(신규 자격증명 없음).
  Google TTS는 한국 리전 미지원으로 배제(stt-tts.md/security.md). 오버랩(LLM↔TTS)은 후속 최적화.
- **출력 프레임**: `CompletionFrame.full_llm_response_text`로 완성 텍스트를 1회 전달(대화 이력).
- **실패 처리**: gRPC status로 스트림을 끊지 않고 `ErrorFrame`(STT/LLM/TTS 단계)을 흘린 뒤 정상 종료한다(grpc.md).
  TTS 실패 시에도 완성 텍스트를 실어 보내고, 이미 보낸 청크가 있으면 `recoverable=True`.

범위 밖(후속): 단계 간 오버랩, 인지지표 Kafka publish(Phase 4), 응급 키워드 가드레일(RAG 측 TBD).

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `GRPC_HOST`/`GRPC_PORT` | `0.0.0.0`/`50051` | 외부 진입 gRPC 바인딩 |
| `RAG_SERVER_TARGET` | `localhost:50052` | RAG 유닛(①) gRPC 타깃. 클러스터는 `rag-server:50052` |
| `LLM_SERVER_TARGET` | `localhost:50053` | LLM 유닛(②) gRPC 타깃. 클러스터는 `llm-server:50053` |
| `LANGUAGE_CODE` | `ko-KR` | 대화 언어 (STT 언어로도 사용) |
| `SYSTEM_PROMPT` | (윌슨 기본 페르소나) | LLM 시스템 프롬프트. 비판단·비교정 원칙 반영 |
| `AZURE_SPEECH_KEY` | (없음) | **필수** Azure Speech 키(STT·TTS 공용). 로컬 `.env`, 배포 K8s Secret. 커밋·로그 금지 |
| `AZURE_SPEECH_REGION` | `koreacentral` | Azure Speech 리전. 한국 고정(PIPA) |
| `TTS_VOICE` | `ko-KR-SunHiNeural` | Azure TTS ko-KR neural 음성 |
| `TTS_OUTPUT_FORMAT` | `audio-24khz-48kbitrate-mono-mp3` | TTS 출력 코덱(앱 재생과 정합 필요) |

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

## 라이브 STT 스모크 (Azure 키 필요)

`.env`에 `AZURE_SPEECH_KEY`를 넣고, WAV(PCM) 또는 OGG-OPUS 파일 하나로 실제 전사를 확인한다:

```powershell
$env:PYTHONPATH="services/orchestrator-server/src"
python services/orchestrator-server/scripts/smoke_stt.py <오디오파일.wav>
```
→ `전사: ...` 와 `OK` 가 출력되면 STT 연동 성공.

## 라이브 TTS 스모크 (Azure 키 필요 — STT와 동일 키)

```powershell
$env:PYTHONPATH="services/orchestrator-server/src"
python services/orchestrator-server/scripts/smoke_tts.py out.mp3
```
→ `저장: out.mp3 (...bytes)` 와 `OK` 가 출력되면 TTS 연동 성공.

> 실제 RAG+LLM 연동 라이브 확인은 두 유닛(+ ChromaDB, NVIDIA 키)을 띄운 뒤
> `RAG_SERVER_TARGET`/`LLM_SERVER_TARGET`을 맞추고 위 `main`을 실행해 BE 클라이언트로 호출한다.
