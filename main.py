from fastapi import FastAPI
from core.config import settings
from services.flight.router import router as flight_router
from services.reservation.router import router as reservation_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend modular con alcance mínimo funcional y control de concurrencia."
)

# Incluir los routers de los servicios lógicos
app.include_router(flight_router, prefix="/api/v1")
app.include_router(reservation_router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "status": "online",
        "documentation": "/docs"
    }