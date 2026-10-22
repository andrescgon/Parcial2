-- Esquema transaccional (RDS PostgreSQL). Se aplica desde la EC2: el RDS es privado.
CREATE TABLE IF NOT EXISTS flights (
    flight_id       VARCHAR(100) PRIMARY KEY,
    route           VARCHAR(20)  NOT NULL,
    origin          VARCHAR(10)  NOT NULL,
    destination     VARCHAR(10)  NOT NULL,
    flight_date     VARCHAR(20)  NOT NULL,   -- texto: el contrato usa YYYY-MM-DD y se compara exacto
    capacity        INT          NOT NULL,
    -- el CHECK es la ultima linea de defensa contra la sobreventa (R2); el UPDATE
    -- condicional del router es la primera.
    seats_available INT          NOT NULL CHECK (seats_available >= 0),
    price_cents     BIGINT       NOT NULL
);

-- R1: la busqueda filtra por estas tres columnas; sin el indice el p95 se cae con 20 clientes.
CREATE INDEX IF NOT EXISTS idx_flights_search ON flights (origin, destination, flight_date);

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id SERIAL       PRIMARY KEY,
    flight_id      VARCHAR(100) NOT NULL REFERENCES flights(flight_id),
    passenger_name VARCHAR(255) NOT NULL,
    fare_class     VARCHAR(50)  NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'CONFIRMED',
    created_at     TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reservations_flight ON reservations (flight_id);
