# LLM 유닛 (②)

역할:

- 오케스트레이터(③)가 `llm/v1` `Generate`로 호출 → RAG 컨텍스트+사용자 발화를 LLM에 전달
- 토큰 스트림을 내부 gRPC(`TokenChunk`) 스트림으로 오케스트레이터에 반환
- **프로바이더 추상화**: 현재 백엔드 = **NVIDIA NIM**(OpenAI 호환 무료 엔드포인트). 나중에 로컬/타사로 교체해도 `provider.py`의 `stream_tokens` 인터페이스만 유지하면 servicer 무변경.

> 디렉터리명 `llm-server`는 프로바이더 중립. 현재 백엔드 = NVIDIA NIM(추상화 뒤 — 나중에 로컬/타사 교체 가능).

## 환경 변수 (실키는 절대 커밋 금지)

| 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `NVIDIA_API_KEY` | ✅ | (없음) | NVIDIA NIM API 키. **로컬은 `.env`(gitignore됨), 배포는 K8s Secret.** 코드·로그·git에 절대 안 남긴다. **이 유닛만 보유.** |
| `NVIDIA_BASE_URL` | | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM OpenAI 호환 엔드포인트 |
| `LLM_MODEL` | | `openai/gpt-oss-120b` | 모델 ID(NVIDIA 페이지 스니펫의 정확한 문자열). 교체는 이 값만 바꾸면 됨 |
| `GRPC_HOST`/`GRPC_PORT` | | `0.0.0.0`/`50053` | gRPC 바인딩 |
| `LLM_TEMPERATURE`/`LLM_TOP_P`/`LLM_MAX_TOKENS` | | `0.6`/`0.95`/`1024` | 생성 파라미터 |

`.env` 예시(로컬 — **커밋 금지, .gitignore로 이미 무시됨**):
```env
NVIDIA_API_KEY=nvapi-여기에_발급받은_키
```

## 실행

```powershell
# 1) proto 스텁 생성(최초 1회 / proto 변경 시)
python services/llm-server/scripts/gen_proto.py

# 2) 의존성
pip install -r services/llm-server/requirements.txt

# 3) 로컬 .env에 NVIDIA_API_KEY 넣고 실행
$env:PYTHONPATH="services/llm-server/src"
python -m wilson_llm.main
```

## 라이브 스모크 (키 필요)

`.env`에 `NVIDIA_API_KEY`를 넣은 뒤:

```powershell
$env:PYTHONPATH="services/llm-server/src"
python services/llm-server/scripts/smoke_live.py
```
→ NVIDIA NIM에 실제 호출해 한국어 응답이 스트리밍되면 성공.

> 키 없이 되는 gRPC 배선(Generate 스트리밍)은 fake 프로바이더 왕복 테스트로 이미 검증됨.
