# IoT-pipeline

![Grafana-dashboard](grafana/dashboard.png)

Tar emot mätvärden från växthuset, lagrar dem och visar dem i realtid.

Pico 2 W → Mosquitto (MQTT) → consumer → TimescaleDB → Grafana

Picon publicerar mätvärden till en MQTT-broker. En consumer prenumererar
på topicen, tolkar meddelandena och skriver dem till TimescaleDB. Grafana
läser databasen och visar dem som grafer och KPI:er.

Brokern i mitten gör att Picon inte behöver känna till databasen. Fler
sensorer eller fler mottagare kan läggas till utan att något annat ändras.

## Komponenter

| Tjänst | Port | Roll |
|---|---|---|
| Mosquitto | 1883 | MQTT-broker, tar emot och distribuerar meddelanden |
| TimescaleDB | 5432 | Tidsseriedatabas, lagrar mätvärden |
| Grafana | 3000 | Visualisering |

## Komma igång

Kräver Docker Desktop och [uv](https://docs.astral.sh/uv/).

Starta infrastrukturen:

    cd src_pipeline
    docker compose up -d

Skapa databastabellen (behövs bara första gången):

    docker exec -i pico_timescaledb psql -U pico -d sensordata < init_db.sql

Installera Python-beroenden och starta consumern:

    uv sync
    uv run consumer.py

Grafana finns på http://localhost:3000 (admin/admin).

Importera dashboarden från `grafana/dashboard.json` via Dashboards → New → Import.

## Testa utan hårdvara

`fake_pico.py` publicerar påhittade mätvärden, så att pipelinen kan testas
innan Picon är inkopplad:

    uv run fake_pico.py

## MQTT-format

Topic: `greenhouse/data`

    {
      "temperature": 24.0,
      "humidity": 45,
      "soil_moisture": 38,
      "water_level": 72,
      "fan_on": false,
      "pump_on": true
    }

## Att tänka på

- Picon kan inte ansluta till `localhost` — den behöver datorns IP-adress
  på nätverket där brokern körs.
- Mosquitto sparar inga meddelanden. Consumern måste vara igång innan
  Picon börjar publicera, annars går de första mätvärdena förlorade.
- Lösenordet i `docker-compose.yaml` är ett utvecklingslösenord och ska
  bytas om pipelinen körs skarpt.