#!/usr/bin/env python3
"""Ejecuta SQL en Athena y espera el resultado.

    python scripts/athena_run.py "SELECT count(*) FROM reservations_curated"
    echo "MSCK REPAIR TABLE reservations_curated" | python scripts/athena_run.py -

Sale con codigo 1 si la consulta falla, para poder encadenarlo en un script.
"""
import os
import sys
import time

import boto3

REGION = os.environ.get("REGION", "us-east-1")
DATABASE = os.environ.get("ATHENA_DATABASE", "airline_analytics")
OUTPUT = os.environ.get("ATHENA_OUTPUT", "")


def run(sql, database=DATABASE, output=OUTPUT, workgroup="primary", timeout=300):
    cl = boto3.client("athena", region_name=REGION)
    kw = {"QueryString": sql, "WorkGroup": workgroup,
          "QueryExecutionContext": {"Database": database}}
    if output:
        kw["ResultConfiguration"] = {"OutputLocation": output}
    qid = cl.start_query_execution(**kw)["QueryExecutionId"]

    t0 = time.time()
    while True:
        qe = cl.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = qe["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        if time.time() - t0 > timeout:
            raise TimeoutError("la consulta " + qid + " sigue en " + state)
        time.sleep(1)

    scanned = qe.get("Statistics", {}).get("DataScannedInBytes", 0)
    if state != "SUCCEEDED":
        raise RuntimeError(state + ": " + str(qe["Status"].get("StateChangeReason")))

    rows = []
    for page in cl.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for r in page["ResultSet"]["Rows"]:
            rows.append([c.get("VarCharValue") for c in r["Data"]])
    return rows, scanned


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sql = sys.stdin.read() if sys.argv[1] == "-" else sys.argv[1]
    try:
        rows, scanned = run(sql)
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
    print("escaneado: " + format(scanned, ",") + " bytes")
    for r in rows[:50]:
        print("  " + " | ".join("" if c is None else c for c in r))


if __name__ == "__main__":
    main()
