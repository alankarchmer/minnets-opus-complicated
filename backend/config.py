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
    
    # Retrieval settings
    max_anchors: int = 5
    min_similarity_threshold: float = 0.65
    max_similarity_threshold: float = 0.85
    max_suggestions: int = 3
    
    # OpenAI
    openai_model: str = "gpt-4.1"
    openai_embedding_model: str = "text-embedding-3-small"
    
    # Orthogonal Search settings
    # Enable orthogonal search in the main /analyze endpoint
    orthogonal_enabled: bool = True
    # Noise injection: σ for Gaussian perturbation (0.15 = ~15-25% off original direction)
    orthogonal_noise_scale: float = 0.15
    # Enable archetype-based cross-domain search
    orthogonal_archetype_enabled: bool = True
    # Target domains for cross-domain vibe search (empty = all domains)
    orthogonal_target_domains: list[str] = [
        "restaurants", "music", "films", "books", "travel", 
        "architecture", "fashion", "experiences"
    ]
    # Temperature for vibe extraction (higher = more creative connections)
    orthogonal_vibe_temperature: float = 0.8
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

