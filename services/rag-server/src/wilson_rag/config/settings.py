from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50052

    chroma_host: str = "chroma-db"
    chroma_port: int = 8000
    chroma_ssl: bool = False
    chroma_tenant: str = "default_tenant"
    chroma_database: str = "default_database"
    chroma_connect_timeout_seconds: float = 30.0

    # dense 검색
    embedding_model_name: str = "cl-nagoya/ruri-v3-310m"
    search_top_k: int = 5  # ASSUMPTION: 컬렉션당 검색 결과 수 기본값, 조정 가능

    # 하이브리드(dense+BM25) RRF 융합 상수. score = 1/(k+rank). 표준 기본값 60.
    rrf_k: int = 60

    # elder/guardian(private) 스코프 필터에 쓸 메타데이터 키.
    # write측(memory-state)/ERD 미확정이라 기본은 빈 값 = private 검색 비활성.
    # 빈 값인 동안에는 스코프 없이 private 컬렉션을 검색하지 않는다(개인정보 유출 방지).
    scope_metadata_field: str = ""  # 확정 후 예: "target_user_id"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
