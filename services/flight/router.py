from fastapi import APIRouter, HTTPException, Query
from core.database import get_db

router = APIRouter(prefix="/flights", tags=["Flight Service"])

@router.get("/search")
def search_flights(
    origin: str = Query(..., description="Código IATA del aeropuerto de origen (ej. BOG)"),
    destination: str = Query(..., description="Código IATA del aeropuerto de destino (ej. MDE)"),
    date: str = Query(..., description="Fecha del vuelo en formato YYYY-MM-DD")
):
    """
    Busca instancias de vuelos disponibles según origen, destino y fecha,
    trayendo la hora de salida y llegada desde el vuelo programado (ScheduledFlight).
    """
    query = """
        SELECT 
            fi.flight_instance_id,
            sf.flight_number,
            a1.code AS origin_code,
            a1.city AS origin_city,
            a2.code AS destination_code,
            a2.city AS destination_city,
            fi.flight_date,
            sf.departure_time,
            sf.arrival_time,
            fi.status
        FROM flight_instance fi
        JOIN scheduled_flight sf ON fi.scheduled_flight_id = sf.scheduled_flight_id
        JOIN route r ON sf.route_id = r.route_id
        JOIN airport a1 ON r.origin_airport_id = a1.airport_id
        JOIN airport a2 ON r.destination_airport_id = a2.airport_id
        WHERE a1.code = %s 
          AND a2.code = %s 
          AND fi.flight_date = %s
          AND fi.status = 'SCHEDULED';
    """
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (origin.upper(), destination.upper(), date))
            flights = cursor.fetchall()
            return {"count": len(flights), "flights": flights}