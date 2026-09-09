import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema de Reservas Aéreas - Backend Modular"
    VERSION: str = "1.0.0"
    
    # Configuración de PostgreSQL
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "sistema_reservas")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "ClaveLocal123")
    DB_PORT: str = os.getenv("DB_PORT", "5432")

    class Config:
        case_sensitive = True

settings = Settings()