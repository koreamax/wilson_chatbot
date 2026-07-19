from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 외부(BE→AI) 진입 gRPC 서버 바인딩. k8s containerPort=50051.
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051  # orchestrator=50051 (rag=50052, llm=50053)

    # 내부 유닛 타깃 (env: RAG_SERVER_TARGET / LLM_SERVER_TARGET).
    # 로컬 기본은 localhost, 클러스터는 service DNS(rag-server:50052 등)를 env로 주입한다.
    rag_server_target: str = "localhost:50052"
    llm_server_target: str = "localhost:50053"

    # 대화 언어. 한국어 고정이나 확장 대비 env(LANGUAGE_CODE)로 노출. STT 언어로도 쓰인다.
    language_code: str = "ko-KR"

    # Azure Speech STT. 실키는 env로만 주입 — 하드코딩·커밋·로그 금지(security.md).
    # 리전은 한국(koreacentral) 고정 — PIPA 국외이전 회피(security.md).
    azure_speech_key: str = ""  # env: AZURE_SPEECH_KEY (필수, 로컬 .env / 배포 K8s Secret)
    azure_speech_region: str = "koreacentral"  # env: AZURE_SPEECH_REGION

    # LLM 시스템 프롬프트(윌슨 페르소나). 비판단·비교정 원칙(CLAUDE.md §1)을 반영한 초기값.
    # ASSUMPTION: 최소 페르소나 — 안전·임상(응급 템플릿 등) 확정 시 교체. 조정 가능.
    system_prompt: str = (
        "당신은 인지 저하가 있는 어르신과 대화하는 음성 돌봄 도우미 '윌슨'입니다. "
        "어르신의 실수나 반복되는 질문을 절대 지적하거나 교정하지 마세요. "
        "언제나 따뜻하고 존중하는 말투로, 짧고 분명한 한국어 문장으로 답하세요."
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
