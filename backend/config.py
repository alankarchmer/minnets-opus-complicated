from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    openai_api_key: str
    supermemory_api_key: str
    exa_api_key: str
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Supermemory
    supermemory_base_url: str = "https://api.supermemory.ai"
    
    # Retrieval settings
    max_anchors: int = 5
    min_similarity_threshold: float = 0.65
    max_similarity_threshold: float = 0.85
    max_suggestions: int = 3
    
    # OpenAI
    openai_model: str = "gpt-4.1"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

