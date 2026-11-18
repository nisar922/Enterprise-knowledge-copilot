from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Enterprise Knowledge Copilot"
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    upload_dir: str = "uploads"
    max_upload_mb: int = 10
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    embedding_model : str = "sentence-transformers/all-MiniLM-L6-v2"
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.8-flash"
    reranked_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    enable_query_rewrite: bool = True
    retrieve_k: int = 20
    final_k: int = 5
    min_relevance_score: float = -3.0
    cost_per_1m_input_tokens: float = 0.10
    cost_per_1m_output_tokens: float = 0.40
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()    