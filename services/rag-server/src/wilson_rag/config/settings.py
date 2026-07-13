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
    embedding_model_name: str = "nlpai-lab/KURE-v1"  # 한국어, 1024차원, 프리픽스 없음
    search_top_k: int = 5  # ASSUMPTION: 컬렉션당 검색 결과 수 기본값, 조정 가능

    # 하이브리드(dense+BM25) RRF 융합 상수. score = 1/(k+rank). 표준 기본값 60.
    rrf_k: int = 60

    # elder 스코프 필터·저장에 쓸 소유자 메타데이터 키. write(저장)와 read(검색)가
    # 같은 키를 써야 스코프 검색이 성립한다. 팀 합의로 노인 가명 ID인 `target_user_id`로 확정.
    # 빈 값이면 elder 검색을 스킵하고 저장도 거부한다(유출·유령데이터 방지 안전장치).
    # 주의: 데이터가 쌓인 뒤 이 값을 바꾸면 기존 문서는 옛 키를 가져 검색에서 누락된다 —
    # 변경 시 elder 재색인이 필요하다. guardian은 ERD 미확정이라 이 값과 무관하게 아직 검색 안 함.
    scope_metadata_field: str = "target_user_id"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
