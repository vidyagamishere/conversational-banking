from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+psycopg://banking_user:banking_pass@yamanote.proxy.rlwy.net:53234/conversational_banking"
    
    # JWT
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 30
    
    # Ollama
    ollama_api_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"
    ollama_retry_attempts: int = 3
    ollama_retry_backoff_seconds: int = 1
    
    # Application
    backend_port: int = 8000
    pin_max_attempts: int = 3

    class Config:
        env_file = "../.env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
