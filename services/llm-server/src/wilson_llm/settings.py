from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50053  # LLM 유닛 포트 (rag=50052, llm=50053)

    # NVIDIA NIM (OpenAI 호환 엔드포인트). 실키는 env로만 주입 — 하드코딩·커밋·로그 금지.
    # env: NVIDIA_API_KEY (필수, 로컬은 .env / 배포는 K8s Secret). 여기 기본값은 빈 문자열.
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_model: str = "openai/gpt-oss-120b"

    # 생성 파라미터 (대화 톤). # ASSUMPTION: 초기값, 조정 가능
    llm_temperature: float = 0.6
    llm_top_p: float = 0.95
    llm_max_tokens: int = 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
