import uuid
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # Database
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433

    # Redis
    redis_password: SecretStr
    redis_host: str = "127.0.0.1"
    redis_port: int = 6380

    # LLM
    groq_api_key: SecretStr
    groq_model: str
    llm_reasoning_effort: str | None = "low"
    llm_timeout_seconds: float = 20.0
    llm_max_output_tokens: int = 600
    chat_history_limit: int = 10

    # Voice
    voice_agent_id: uuid.UUID | None = None
    voice_greeting: str = "Hi there! How can I help you today?"
    voice_reasoning_effort: str | None = None
    tts_provider: str = "groq"
    deepgram_api_key: SecretStr | None = None
    deepgram_tts_voice: str = "aura-2-helena-en"

    # Knowledge base (RAG)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = ".models"
    rag_top_k: int = 4
    rag_max_distance: float | None = 0.30


@lru_cache
def get_settings() -> Settings:
    return Settings()