# services/reservation/router.py
from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
import psycopg2
from core.database import get_db
from services.reservation.models import CreateReservationRequest
from services.inventory.service import allocate_seat

router = APIRouter(prefix="/reservations", tags=["Reservation & Inventory Service"])

@router.post("", status_code=status.HTTP_201_CREATED)
def create_reservation(payload: CreateReservationRequest):
    """
    Crea un pasajero dinámicamente si no existe, abre la reserva con canal y expiración de 15 min,
    genera los segmentos de itinerario, calcula tarifas, bloquea asientos (concurrencia) y registra outbox.
    """
    with get_db() as conn:
        with conn.cursor() as cursor:
            try:
                hold_expires = datetime.utcnow() + timedelta(minutes=15)
                booking_channel = payload.booking_channel.upper()
                agent_id = payload.agent_id if booking_channel == "AGENCY" else None

                # 1. Registrar o actualizar pasajero al vuelo (On-the-fly checkout)
                cursor.execute(
                    """
                    INSERT INTO passenger (first_name, last_name, date_of_birth, document_id, nationality, email, phone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id) DO UPDATE 
                    SET first_name = EXCLUDED.first_name, 
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone
                    RETURNING passenger_id;
                    """,
                    (
                        payload.passenger.first_name,
                        payload.passenger.last_name,
                        payload.passenger.date_of_birth,
                        payload.passenger.document_id,
                        payload.passenger.nationality,
                        payload.passenger.email,
                        payload.passenger.phone
                    )
                )
                pass_row = cursor.fetchone()
                passenger_id = pass_row["passenger_id"] if isinstance(pass_row, dict) else pass_row[0]

                # 2. Calcular monto total consultando los precios de los fares
                total_amount = 0.0
                item_details = []
                for item in payload.items:
                    cursor.execute("SELECT price FROM fare WHERE fare_id = %s;", (item.fare_id,))
                    fare_row = cursor.fetchone()
                    if not fare_row:
                        raise HTTPException(status_code=404, detail=f"Tarifa con ID {item.fare_id} no encontrada.")
                    price = float(fare_row["price"] if isinstance(fare_row, dict) else fare_row[0])
                    item_details.append((item, price))
                    total_amount += price

                # 3. Crear cabecera de reserva (respetando restricciones CHECK)
                cursor.execute(
                    """
                    INSERT INTO reservation (agent_id, booking_channel, status, total_amount, created_at, hold_expires_at)
                    VALUES (%s, %s::booking_channel, 'HELD', %s, CURRENT_TIMESTAMP, %s)
                    RETURNING reservation_id;
                    """,
                    (agent_id, booking_channel, total_amount, hold_expires)
                )
                res_row = cursor.fetchone()
                reservation_id = res_row["reservation_id"] if isinstance(res_row, dict) else res_row[0]

                # 4. Asociar pasajero a la reserva
                cursor.execute(
                    """
                    INSERT INTO reservation_passenger (reservation_id, passenger_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (reservation_id, passenger_id)
                )

                # 5. Procesar ítems, segmentos de itinerario, bloqueo de inventario y detalle comercial
                for item, price in item_details:
                    # Crear segmento de itinerario requerido por la tabla seat_allocation
                    cursor.execute(
                        """
                        INSERT INTO itinerary_segment (reservation_id, flight_instance_id, sequence_number, segment_status)
                        VALUES (%s, %s, %s, 'ACTIVE')
                        RETURNING segment_id;
                        """,
                        (reservation_id, item.flight_instance_id, item.sequence_number)
                    )
                    seg_row = cursor.fetchone()
                    segment_id = seg_row["segment_id"] if isinstance(seg_row, dict) else seg_row[0]

                    # Bloquear asiento (Inventory Service / Concurrencia con índice único parcial)
                    allocate_seat(
                        cursor=cursor,
                        segment_id=segment_id,
                        flight_instance_id=item.flight_instance_id,
                        aircraft_id=item.aircraft_id,
                        passenger_id=passenger_id,
                        seat_id=item.seat_id
                    )

                    # Registrar detalle comercial de la reserva
                    cursor.execute(
                        """
                        INSERT INTO reservation_item 
                        (reservation_id, passenger_id, segment_id, fare_id, amount)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (reservation_id, passenger_id, segment_id, item.fare_id, price)
                    )

                # 6. Registrar historial de estado inicial
                cursor.execute(
                    """
                    INSERT INTO reservation_status_history (reservation_id, status, status_date, notes)
                    VALUES (%s, 'HELD', CURRENT_TIMESTAMP, 'Reserva creada en estado HELD')
                    """,
                    (reservation_id,)
                )

                # 7. Registrar evento Outbox en la misma transacción ACID
                import json
                event_payload = {
                    "reservation_id": reservation_id,
                    "passenger_id": passenger_id,
                    "status": "HELD",
                    "total_amount": total_amount,
                    "expires_at": hold_expires.isoformat()
                }
                cursor.execute(
                    """
                    INSERT INTO outbox_event (aggregate_type, aggregate_id, event_type, payload, occurred_at)
                    VALUES ('Reservation', %s, 'ReservationHeld', %s, CURRENT_TIMESTAMP);
                    """,
                    (str(reservation_id), json.dumps(event_payload))
                )

                conn.commit()
                return {
                    "message": "Reserva creada exitosamente en estado HELD",
                    "reservation_id": reservation_id,
                    "passenger_id": passenger_id,
                    "total_amount": total_amount,
                    "hold_expires_at": hold_expires
                }

            except HTTPException as he:
                conn.rollback()
                raise he
            except psycopg2.Error as db_err:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error de base de datos al procesar la reserva: {str(db_err)}"
                )
            except Exception as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error inesperado: {str(e)}"
                )

@router.get("/{reservation_id}")
def get_reservation(reservation_id: int):
    """
    Consulta los detalles de una reserva existente por su ID.
    """
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT reservation_id, agent_id, booking_channel, status, total_amount, created_at, hold_expires_at
                FROM reservation
                WHERE reservation_id = %s;
                """,
                (reservation_id,)
            )
            reservation = cursor.fetchone()
            if not reservation:
                raise HTTPException(status_code=404, detail="Reserva no encontrada")
            return reservation