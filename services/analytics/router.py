from fastapi import APIRouter, HTTPException, Query, status
from services.analytics.service import query_occupancy_from_athena

router = APIRouter(prefix="/analytics", tags=["Analytics Service"])

@router.get("/occupancy")
def get_occupancy(
    route: str = Query(..., description="Ruta en formato ORIGEN-DESTINO (ej. BOG-MDE)"),
    month: str = Query(..., description="Mes en formato YYYY-MM")
):
    """
    Retorna la ocupación calculada desde Amazon Athena para una ruta y mes dados.
    Cumple con el SLA de < 10 segundos requerido por R7.
    """
    data = query_occupancy_from_athena(route=route.strip().upper(), month=month.strip())
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontraron datos analíticos para la ruta {route} en el mes {month}."
        )
    return data

