"""
Testskript som låtsas vara Picon.
Publicerar påhittade mätvärden till Mosquitto så att resten av
pipelinen kan testas utan hårdvara.

Körs med: uv run fake_pico.py
"""

import json
import random
import time

import paho.mqtt.client as mqtt

# Var brokern finns. "localhost" = min egen dator, porten från compose-filen.
BROKER = "localhost"
PORT = 1883

# Facket vi postar i. Måste vara exakt samma sträng som consumern lyssnar på.
TOPIC = "greenhouse/data"

# Startvärden att vandra runt ifrån.
temperature = 24.0
humidity = 45
soil_moisture = 38
water_level = 72

# Skapa en klient och anslut.
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(BROKER, PORT)

print(f"Ansluten till {BROKER}:{PORT}, publicerar till '{TOPIC}'")

while True:
    # Låt värdena vandra lite slumpmässigt istället för att hoppa vilt.
    temperature = round(temperature + random.uniform(-0.5, 0.5), 1)
    humidity = max(0, min(100, humidity + random.randint(-2, 2)))
    soil_moisture = max(0, min(100, soil_moisture + random.randint(-3, 3)))
    water_level = max(0, min(100, water_level - random.randint(0, 1)))

    # Samma beslutslogik som Picon har, så att vi kan testa flaggorna.
    fan_on = temperature > 30
    pump_on = soil_moisture < 30 and water_level > 20

    payload = {
        "temperature": temperature,
        "humidity": humidity,
        "soil_moisture": soil_moisture,
        "water_level": water_level,
        "fan_on": fan_on,
        "pump_on": pump_on,
    }

    # json.dumps gör om Python-objektet till en textsträng.
    client.publish(TOPIC, json.dumps(payload))
    print(payload)

    time.sleep(2)