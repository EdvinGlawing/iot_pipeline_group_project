"""
Consumer: prenumererar på MQTT-topicen och skriver mätvärdena
till TimescaleDB.

Körs med: uv run consumer.py
"""

import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import psycopg

BROKER = "localhost"
PORT = 1883
TOPIC = "greenhouse/data"

# Anslutningssträng till databasen. Värdena kommer från docker-compose.yaml.
DB_CONNECTION = "host=localhost port=5432 dbname=sensordata user=pico password=pico_dev_password"

# SQL-satsen som skriver en rad. %s är platshållare som fylls i av
# psycopg - aldrig genom strängkonkatenering (det öppnar för SQL-injektion).
INSERT_SQL = """
    INSERT INTO sensor_readings
        (time, temperature, humidity, soil_moisture, water_level, fan_on, pump_on)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
"""


def connect_to_database(retries=10, delay=2):
    """
    Försöker ansluta till databasen flera gånger.
    Behövs eftersom containern kan ha startat men inte vara redo att svara.
    """
    for attempt in range(1, retries + 1):
        try:
            connection = psycopg.connect(DB_CONNECTION)
            print("Ansluten till databasen")
            return connection
        except psycopg.OperationalError as error:
            print(f"Databasen svarar inte (försök {attempt}/{retries}): {error}")
            time.sleep(delay)

    raise RuntimeError("Kunde inte ansluta till databasen")


def on_connect(client, userdata, flags, reason_code, properties):
    """Anropas när anslutningen till brokern är klar."""
    print(f"Ansluten till brokern, prenumererar på '{TOPIC}'")
    client.subscribe(TOPIC)


def on_message(client, userdata, message):
    """Anropas varje gång ett meddelande kommer in på topicen."""
    connection = userdata["connection"]

    try:
        data = json.loads(message.payload)
    except json.JSONDecodeError:
        print(f"Kunde inte tolka meddelandet: {message.payload}")
        return

    row = (
        datetime.now(timezone.utc),
        data.get("temperature"),
        data.get("humidity"),
        data.get("soil_moisture"),
        data.get("water_level"),
        data.get("fan_on"),
        data.get("pump_on"),
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(INSERT_SQL, row)
        connection.commit()
        print(f"Sparade: {data}")
    except psycopg.Error as error:
        print(f"Kunde inte skriva till databasen: {error}")
        connection.rollback()


connection = connect_to_database()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.user_data_set({"connection": connection})
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT)

# Blockerar här och låter biblioteket anropa callbacks när det händer något.
client.loop_forever()