"""Cấu hình đọc từ biến môi trường / file .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = 0.0

    database_url: str = "sqlite:///./data/app.db"

    # Chuỗi phân tách bằng dấu phẩy — giữ dạng str để không vướng
    # JSON-parsing của pydantic-settings cho kiểu list.
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
