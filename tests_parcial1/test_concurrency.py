import concurrent.futures
import requests

URL = "http://127.0.0.1:8000/api/v1/reservations"

def create_payload(index: int):
    """Genera un payload único por hilo pero apuntando al mismo asiento."""
    return {
        "booking_channel": "DIRECT",
        "passenger": {
            "first_name": f"Pasajero_{index}",
            "last_name": "Concurrente",
            "date_of_birth": "1990-01-01",
            "document_id": f"CC-CONCURRENCY-{index}",
            "nationality": "Colombian",
            "email": f"user_{index}@test.com",
            "phone": f"+57300000000{index}"
        },
        "items": [
            {
                "flight_instance_id": 1,
                "aircraft_id": 1,
                "seat_id": 2,        # ¡MISMO ASIENTO PARA TODOS!
                "fare_id": 1,
                "sequence_number": 1
            }
        ]
    }

def send_reservation_request(index: int):
    payload = create_payload(index)
    response = requests.post(URL, json=payload)
    return index, response.status_code, response.json()

def run_concurrency_test(total_requests=10):
    print(f"--- Iniciando prueba de concurrencia ({total_requests} hilos simultáneos) ---")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=total_requests) as executor:
        futures = [executor.submit(send_reservation_request, i) for i in range(1, total_requests + 1)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    print("\n--- Resultados de las Peticiones ---")
    successful = 0
    conflicts = 0
    other_errors = 0

    for idx, status_code, data in results:
        print(f"Hilo #{idx} -> Status Code: {status_code} | Response: {data}")
        if status_code == 201:
            successful += 1
        elif status_code == 409:
            conflicts += 1
        else:
            other_errors += 1

    print("\n--- Balance Final de la Prueba ---")
    print(f"Reservas Exitosas (HTTP 201)  : {successful}")
    print(f"Bloqueos por Concurrencia (409): {conflicts}")
    print(f"Otros Errores                 : {other_errors}")

    if successful == 1 and conflicts == (total_requests - 1):
        print("\n ¡ÉXITO TOTAL! El control de concurrencia y el índice único parcial funcionaron perfectamente.")
    else:
        print("\n ALERTA: Hubo sobreventa o comportamientos inesperados.")

if __name__ == "__main__":
    run_concurrency_test(10)