import json
from psycopg2.extensions import connection

def create_outbox_event(conn: connection, aggregate_type: str, event_type: str, payload: dict):
    """
    Inserta un evento en la tabla outbox_event dentro de la transacción activa actual.
    Esto garantiza consistencia fuerte (ACID) antes de que un worker publiqué en RabbitMQ.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO outbox_event (aggregate_type, event_type, payload, status, created_at)
            VALUES (%s, %s, %s, 'PENDING', CURRENT_TIMESTAMP);
            """,
            (aggregate_type, event_type, json.dumps(payload))
        )