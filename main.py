import os
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from core.config import settings
from services.flight.router import router as flight_router
from services.reservation.router import router as reservation_router
from services.analytics.router import router as analytics_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Airline Reservation System - Backend and Analytics Panel"
)

# Incluir routers según los contratos de la API
app.include_router(flight_router)
app.include_router(reservation_router)
app.include_router(analytics_router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/health", status_code=200)
def health_check():
    """Endpoint de salud requerido por el contrato."""
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Sirve la interfaz de cliente para búsqueda y reserva de vuelos."""
    index_path = os.path.join(BASE_DIR, "frontend", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/manager", response_class=HTMLResponse)
def read_manager():
    """Sirve el panel gerencial para visualización de métricas y ocupación."""
    manager_path = os.path.join(BASE_DIR, "frontend", "manager.html")
    with open(manager_path, "r", encoding="utf-8") as f:
        return f.read()