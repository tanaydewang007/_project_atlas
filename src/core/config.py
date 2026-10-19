from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Project Atlas Report Copilot"
    db_path: str = "src/data/atlas.db"
    chroma_path: str = "src/data/chroma"
    reports_dir: str = "src/data/reports"
    embedding_backend: Literal["default", "hash"] = "default"
    auto_ingest_on_start: bool = True

    api_keys: str = ""

    llm_provider: Literal["none", "ollama", "bedrock", "anthropic", "openai", "gemini", "custom"] = "none"
    llm_model: str = ""
    bedrock_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""
    ollama_base_url: str = ""
    ollama_model: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_max_tokens: int = 700
    llm_timeout_s: float = 20.0
    request_token_cap: int = 6000
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    llm_price_in_per_m: float = 0.0
    llm_price_out_per_m: float = 0.0

    request_timeout_s: float = 30.0
    confidence_threshold: float = 0.5
    cache_ttl_s: int = 3600
    sql_row_limit: int = 50
    sql_timeout_s: float = 2.0
    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.15
    chunk_chars: int = 800
    chunk_overlap: int = 120
    log_level: str = "INFO"

    @property
    def api_key_map(self) -> dict[str, str]:
        pairs = (item.split(":", 1) for item in self.api_keys.split(",") if ":" in item)
        return {key.strip(): client.strip() for key, client in pairs}


@lru_cache
def get_settings() -> Settings:
    return Settings()
