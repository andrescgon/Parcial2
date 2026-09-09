# services/reservation/models.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class PassengerCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    document_id: str
    nationality: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class ReservationItemRequest(BaseModel):
    flight_instance_id: int
    aircraft_id: int
    seat_id: int
    fare_id: int
    sequence_number: int = 1

class CreateReservationRequest(BaseModel):
    booking_channel: str = "DIRECT"  # 'DIRECT' o 'AGENCY'
    agent_id: Optional[int] = None   # Obligatorio si booking_channel es 'AGENCY'
    passenger: PassengerCreate
    items: List[ReservationItemRequest]