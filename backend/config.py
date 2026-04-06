from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Voice
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    picovoice_access_key: str = ""

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    llm_provider: str = "anthropic"  # anthropic | gemini | ollama

    # Tools
    openweather_api_key: str = ""
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    home_assistant_url: str = ""
    home_assistant_token: str = ""
    alpha_vantage_api_key: str = ""
    google_maps_api_key: str = ""

    # Storage
    redis_url: str = "redis://localhost:6379"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    chroma_persist_dir: str = "./data/chroma"
    sqlite_db_path: str = "./data/jarvis.db"

    # Mode
    local_mode: bool = False
    ollama_base_url: str = "http://localhost:11434"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
