from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/financial_ledger"
    
    # App
    APP_NAME: str = "Financial Ledger API"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    
    class Config:
        env_file = ".env"


settings = Settings()
