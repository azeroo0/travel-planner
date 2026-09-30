from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None

    # 브라우저에서 이 API를 부를 수 있는 프론트 주소. 쉼표로 구분 (예: http://localhost:3000,https://dev.example.com)
    cors_origins: str = "http://localhost:3000"

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
    recommendation_model_timeout_seconds: float = 15.0  # 추천의 요구사항 해석이 이보다 오래 걸리면 키워드 규칙으로 대체

    # 평가 파이프라인 결과 (evaluation/runs/<실행>/automatic_metrics.json)
    experiments_metrics_path: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
