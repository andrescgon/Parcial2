from pydantic import BaseModel

class AdminFlightCreate(BaseModel):
    flight_id: str
    route: str
    flight_date: str
    capacity: int
    price_cents: int

class FlightSearchItem(BaseModel):
    flight_id: str
    route: str
    flight_date: str
    seats_available: int
    price_cents: int

