from fastapi import APIRouter, HTTPException, Query, status
from typing import List
import psycopg2
from core.database import get_db
from services.flight.models import AdminFlightCreate, FlightSearchItem

router = APIRouter(tags=["Flight Service"])

@router.post("/admin/flights", status_code=status.HTTP_201_CREATED)
def create_admin_flight(flight: AdminFlightCreate):
    """
    Crea un vuelo en el sistema para administración y pruebas del harness.
    Retorna 201 en éxito, o 409 si el flight_id ya existe.
    """
    parts = flight.route.strip().split("-")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La ruta debe tener formato ORIGEN-DESTINO (ej. BOG-MDE)"
        )
    origin, destination = parts[0].strip().upper(), parts[1].strip().upper()

    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO flights (flight_id, route, origin, destination, flight_date, capacity, seats_available, price_cents)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING flight_id, route, flight_date, capacity, price_cents;
                    """,
                    (
                        flight.flight_id,
                        flight.route,
                        origin,
                        destination,
                        flight.flight_date,
                        flight.capacity,
                        flight.capacity,
                        flight.price_cents
                    )
                )
                row = cur.fetchone()
                return {
                    "flight_id": row["flight_id"],
                    "route": row["route"],
                    "flight_date": row["flight_date"],
                    "capacity": row["capacity"],
                    "price_cents": row["price_cents"]
                }
            except psycopg2.IntegrityError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El vuelo {flight.flight_id} ya existe."
                )

@router.get("/flights/search", response_model=List[FlightSearchItem])
def search_flights(
    origin: str = Query(..., description="Código de origen (ej. BOG)"),
    destination: str = Query(..., description="Código de destino (ej. MDE)"),
    date: str = Query(..., description="Fecha del vuelo YYYY-MM-DD")
):
    """
    Búsqueda rápida de vuelos disponibles según origen, destino y fecha.
    Retorna una lista JSON con latencia p95 < 1.0s.
    """
    query = """
        SELECT flight_id, route, flight_date, seats_available, price_cents
        FROM flights
        WHERE origin = %s AND destination = %s AND flight_date = %s
        ORDER BY flight_id;
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (origin.strip().upper(), destination.strip().upper(), date.strip()))
            rows = cur.fetchall()
            return [
                {
                    "flight_id": r["flight_id"],
                    "route": r["route"],
                    "flight_date": r["flight_date"],
                    "seats_available": r["seats_available"],
                    "price_cents": r["price_cents"]
                }
                for r in rows
            ]

@router.get("/admin/flights")
def list_admin_flights():
    """
    Lista los vuelos que todavía tienen asientos, agrupados por ruta y fecha.
    No forma parte del contrato ni lo usa el harness: existe para saber qué
    buscar en el frontend durante una demostración.
    """
    query = """
        SELECT origin, destination, flight_date,
               count(*) AS vuelos,
               sum(seats_available) AS asientos_libres
        FROM flights
        WHERE seats_available > 0
        GROUP BY origin, destination, flight_date
        ORDER BY asientos_libres DESC, flight_date;
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return {
                "para_buscar_en_la_pagina": [
                    {
                        "origen": r["origin"],
                        "destino": r["destination"],
                        "fecha": r["flight_date"],
                        "vuelos": r["vuelos"],
                        "asientos_libres": int(r["asientos_libres"]),
                    }
                    for r in rows
                ],
                "combinaciones": len(rows),
            }
