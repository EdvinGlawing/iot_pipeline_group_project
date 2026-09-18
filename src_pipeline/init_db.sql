-- Tabell för mätvärden från växthuset.
-- Körs en gång för att sätta upp databasen.

CREATE TABLE IF NOT EXISTS sensor_readings (
    time          TIMESTAMPTZ      NOT NULL,
    temperature   REAL,
    humidity      REAL,
    soil_moisture INTEGER,
    water_level   INTEGER,
    fan_on        BOOLEAN,
    pump_on       BOOLEAN
);

-- Gör om tabellen till en hypertable, uppdelad på tid.
SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);