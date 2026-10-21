from pydantic import BaseModel
from typing import Optional, Union

class CreateReservationInput(BaseModel):
    flight_id: str
    passenger_name: str
    fare_class: Optional[str] = "ECONOMY"

class ReservationResponse(BaseModel):
    reservation_id: int
    flight_id: str
    status: str
    passenger_name: str