import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema de Reservas Aéreas - Backend Modular"
    VERSION: str = "1.0.0"
    
    # Configuración de PostgreSQL
    default_host: str = "/tmp/pg_sockets" if os.path.exists("/tmp/pg_sockets/.s.PGSQL.5434") else "localhost"
    default_port: str = "5434" if os.path.exists("/tmp/pg_sockets/.s.PGSQL.5434") else "5432"

    DB_HOST: str = os.getenv("DB_HOST", default_host)
    DB_NAME: str = os.getenv("DB_NAME", "sistema_reservas")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_PORT: str = os.getenv("DB_PORT", default_port)

    # AWS Athena configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    ATHENA_DATABASE: str = os.getenv("ATHENA_DATABASE", "airline_analytics")
    ATHENA_WORKGROUP: str = os.getenv("ATHENA_WORKGROUP", "primary")
    ATHENA_OUTPUT: str = os.getenv("ATHENA_OUTPUT", "")

    class Config:
        case_sensitive = True

settings = Settings()