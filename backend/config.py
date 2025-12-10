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
    
    # Context Judge settings
    # Model for context classification (use mini for speed, full for accuracy)
    context_judge_model: str = "gpt-4o-2024-08-06"
    # Path for training data logging (JSONL format)
    judge_log_path: str = "training_data/router_decisions.jsonl"
    
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
    
    # Vector Math: Principal Component Subtraction (Technique 1)
    # Subtraction intensity: 0=no effect, 1=full removal of dominant components
    pca_lambda_surprise: float = 1.0
    # Minimum memories required for meaningful PCA (fallback to average if fewer)
    pca_min_memories: int = 5
    # Number of dominant components to subtract for serendipity
    pca_num_components: int = 2
    
    # Vector Math: Antonym Steering (Technique 2)
    # Inversion strength: 0=pure taste, 1=strong contrast away from current context
    antonym_alpha: float = 0.5
    # Target vibe anchors for directional steering (instead of pure negation)
    antonym_target_vibes: list[str] = [
        "relaxation", "novelty", "adventure", "intimacy", "chaos"
    ]
    
    # Vector Math: Cross-Modal Bridge (Technique 3)
    # Domain anchors for computing bridge transformation vectors
    bridge_domains: list[str] = [
        "restaurant", "movie", "music", "book", "architecture"
    ]
    
    # Reranking settings
    # Number of broad results to fetch before mathematical reranking
    rerank_pool_size: int = 50
    # Final number of results after reranking
    rerank_top_k: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

