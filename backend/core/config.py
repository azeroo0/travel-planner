from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None

    # 인증 (JWT)
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # 리뷰 분석 모델 (Ollama). OLLAMA_MODEL은 qlora 모델로 사용한다.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str | None = None
    ollama_model_base: str | None = None
    ollama_model_lora: str | None = None
    ollama_timeout_seconds: float = 120.0

    # 평가 파이프라인 결과 (evaluation/runs/<실행>/automatic_metrics.json)
    experiments_metrics_path: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
