import re
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from core.config import settings

# route y month se interpolan en el SQL: se validan con un formato cerrado para que
# no pueda entrar nada mas que tres letras, un guion y tres letras / YYYY-MM.
ROUTE_RE = re.compile(r"^[A-Z]{3}-[A-Z]{3}$")
MONTH_RE = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")


def query_occupancy_from_athena(route: str, month: str):
    """Lee la ocupacion de route_month_metrics en Athena (R7).

    Devuelve None si no hay datos (-> 404 en el router) y lanza 503 si Athena falla:
    nunca inventa un valor.
    """
    if not ROUTE_RE.match(route) or not MONTH_RE.match(month):
        return None

    query = (
        "SELECT route, month, occupancy, seats_sold, seats_capacity "
        "FROM route_month_metrics "
        f"WHERE route = '{route}' AND month = '{month}' LIMIT 1"
    )
    params = {
        "QueryString": query,
        "QueryExecutionContext": {"Database": settings.ATHENA_DATABASE},
        "WorkGroup": settings.ATHENA_WORKGROUP,
    }
    if settings.ATHENA_OUTPUT:
        params["ResultConfiguration"] = {"OutputLocation": settings.ATHENA_OUTPUT}

    try:
        client = boto3.client("athena", region_name=settings.AWS_REGION)
        qid = client.start_query_execution(**params)["QueryExecutionId"]

        # R7 exige responder en menos de 10 s: se corta el sondeo a los 9.
        deadline = time.monotonic() + 9.0
        state = "QUEUED"
        while time.monotonic() < deadline:
            state = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(0.2)

        if state != "SUCCEEDED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Athena no respondio correctamente (estado {state}, consulta {qid}).",
            )

        rows = client.get_query_results(QueryExecutionId=qid)["ResultSet"]["Rows"]
        if len(rows) < 2:
            return None

        cols = [c.get("VarCharValue") for c in rows[1]["Data"]]
        return {
            "route": cols[0],
            "month": cols[1],
            "occupancy": float(cols[2]),
            "seats_sold": int(cols[3]),
            "seats_capacity": int(cols[4]),
        }
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error consultando Athena: {type(exc).__name__}",
        )
