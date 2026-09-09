# services/inventory/service.py
import psycopg2
from fastapi import HTTPException, status

def allocate_seat(cursor, segment_id: int, flight_instance_id: int, aircraft_id: int, passenger_id: int, seat_id: int):
    """
    Intenta bloquear el asiento respetando el índice único parcial 'uq_active_seat_allocation'.
    Si el asiento ya está HELD o CONFIRMED, la BD lanza IntegrityError -> HTTP 409 Conflict.
    """
    try:
        cursor.execute(
            """
            INSERT INTO seat_allocation 
            (segment_id, flight_instance_id, aircraft_id, passenger_id, seat_id, status, allocation_date)
            VALUES (%s, %s, %s, %s, %s, 'HELD', CURRENT_TIMESTAMP)
            RETURNING allocation_id;
            """,
            (segment_id, flight_instance_id, aircraft_id, passenger_id, seat_id)
        )
        row = cursor.fetchone()
        return row["allocation_id"] if isinstance(row, dict) else row[0]
    except psycopg2.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de concurrencia: El asiento seleccionado ya se encuentra ocupado o retenido."
        )