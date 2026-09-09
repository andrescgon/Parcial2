from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from core.config import settings

def get_db_connection():
    """Establece y retorna una conexión directa a PostgreSQL."""
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        port=settings.DB_PORT,
        cursor_factory=RealDictCursor
    )
    return conn

@contextmanager
def get_db():
    """
    Context manager para manejar transacciones ACID de forma segura.
    Realiza commit automático si no hay excepciones, o rollback en caso de error.
    """
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()