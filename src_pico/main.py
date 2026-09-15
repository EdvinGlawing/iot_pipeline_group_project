from dht import DHT11
from machine import Pin, I2C, ADC
from neopixel import NeoPixel
from wifi import connect_wifi
from umqtt.simple import MQTTClient
import time
import json


# WIFI / MQTT
MQTT_BROKER = "172.20.10.4"   # IP Adress
MQTT_PORT = 1883
MQTT_TOPIC = b"greenhouse"
MQTT_CLIENT_ID = "greenhouse-pico"

# Skicka data var 5:e sekund
MQTT_INTERVAL = 5000

mqtt_client = None
last_mqtt_publish = 0


def connect_mqtt():
    try:
        client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_BROKER,
            port=MQTT_PORT
        )

        client.connect()

        print("Connected to MQTT broker")

        return client

    except Exception as error:
        print("MQTT connection failed:", error)
        return None


# DHT11
sensor = DHT11(Pin(16))


# WS2812
NUM_LEDS = 8
strip = NeoPixel(Pin(15), NUM_LEDS)

OFF = (0, 0, 0)

COLORS = [
    (0, 0, 255),      # LED 1 blå
    (0, 0, 255),      # LED 2 blå
    (0, 255, 0),      # LED 3 grön
    (0, 255, 0),      # LED 4 grön
    (255, 150, 0),    # LED 5 gul
    (255, 150, 0),    # LED 6 gul
    (255, 0, 0),      # LED 7 röd
    (255, 0, 0)       # LED 8 röd
]

TEMP_PER_LED = 5


def scale_color(color, brightness):
    return tuple(int(value * brightness) for value in color)


def update_temperature_bar(temp):
    for i in range(NUM_LEDS):
        strip[i] = OFF

    # Minusgrader -> visa blått
    if temp < 0:
        strip[0] = (0, 0, 80)
        strip.write()
        return

    # 40 grader eller mer -> fullt
    if temp >= 40:
        for i in range(NUM_LEDS):
            strip[i] = COLORS[i]

        strip.write()
        return

    position = temp / TEMP_PER_LED

    full_leds = int(position)
    partial = position - full_leds

    for i in range(full_leds):
        strip[i] = COLORS[i]

    if full_leds < NUM_LEDS:
        brightness = max(partial, 0.05)

        strip[full_leds] = scale_color(
            COLORS[full_leds],
            brightness
        )

    strip.write()


# LCD
i2c = I2C(
    0,
    sda=Pin(0),
    scl=Pin(1),
    freq=100000
)

LCD_ADDR = 0x27
BACKLIGHT = 0x08
ENABLE = 0x04
RS = 0x01


def write4(data):
    i2c.writeto(
        LCD_ADDR,
        bytes([data | BACKLIGHT | ENABLE])
    )

    time.sleep_us(1)

    i2c.writeto(
        LCD_ADDR,
        bytes([data | BACKLIGHT])
    )

    time.sleep_us(50)


def send(value, mode=0):
    high = (value & 0xF0) | mode
    low = ((value << 4) & 0xF0) | mode

    write4(high)
    write4(low)


def command(value):
    send(value, 0)


def write_char(char):
    send(ord(char), RS)


def write_text(text):
    for char in text:
        write_char(char)


def set_cursor(row, col):
    address = 0x00 if row == 0 else 0x40
    command(0x80 | (address + col))


def lcd_init():
    time.sleep_ms(50)

    write4(0x30)
    time.sleep_ms(5)

    write4(0x30)
    time.sleep_us(150)

    write4(0x30)
    write4(0x20)

    command(0x28)
    command(0x0C)
    command(0x06)
    command(0x01)

    time.sleep_ms(2)


def pad_line(text):
    text = str(text)

    if len(text) < 16:
        text += " " * (16 - len(text))

    return text[:16]


# Fläkt
fan_led = Pin(14, Pin.OUT)

HIGH_TEMP = 30
LOW_TEMP = 28
HOT_TIME_REQUIRED = 5

hot_since = None
fan_on = False


# Pump / Simulerad jordfuktighet + vatten nivå
soil_sensor = ADC(26)
water_sensor = ADC(27)

pump_led = Pin(13, Pin.OUT)

DRY_LIMIT = 30
WET_LIMIT = 45
DRY_TIME_REQUIRED = 5

dry_since = None
pump_on = False

MIN_WATER_LEVEL = 20


# Start LCD
lcd_init()


# Connect WIFI
print("Connecting to WiFi...")

wifi_connected = False

try:
    wifi_connected = connect_wifi()
except Exception as error:
    print("WiFi error:", error)

if wifi_connected:
    print("WiFi connected")
else:
    print("WiFi connection failed")


# Connect MQTT
if wifi_connected:
    mqtt_client = connect_mqtt()


# Start MQTT timer
last_mqtt_publish = time.ticks_ms()


while True:

    # Läs sensorer
    sensor.measure()

    temperature = sensor.temperature()
    humidity = sensor.humidity()

    soil_raw = soil_sensor.read_u16()
    soil_percent = int((soil_raw / 65535) * 100)

    water_raw = water_sensor.read_u16()
    water_percent = int((water_raw / 65535) * 100)

    print(f"Temperature: {temperature:.1f} C")
    print(f"Humidity: {humidity:.1f} %")
    print(f"Soil moisture: {soil_percent}%")
    print(f"Water level: {water_percent}%")



    # WS2812
    update_temperature_bar(temperature)



    # Fäktlogik
    current_time = time.time()

    if temperature > HIGH_TEMP:
        if hot_since is None:
            hot_since = current_time

        if current_time - hot_since >= HOT_TIME_REQUIRED:
            fan_on = True

    else:
        hot_since = None

    if temperature < LOW_TEMP:
        fan_on = False

    if fan_on:
        fan_led.on()
    else:
        fan_led.off()


    # Pumplogik
    if soil_percent < DRY_LIMIT:
        if dry_since is None:
            dry_since = current_time

        if current_time - dry_since >= DRY_TIME_REQUIRED:
            if water_percent > MIN_WATER_LEVEL:
                pump_on = True
            else:
                pump_on = False

    else:
        dry_since = None

    if soil_percent > WET_LIMIT:
        pump_on = False

    # Extra säkerhet:
    # Om vattennivån blir för låg stängs pumpen direkt av
    if water_percent <= MIN_WATER_LEVEL:
        pump_on = False

    if pump_on:
        pump_led.on()
    else:
        pump_led.off()


    # LCD rad 1
    display_page = (time.ticks_ms() // 2000) % 2

    set_cursor(0, 0)

    if display_page == 0:
        line1 = f"T:{temperature:.1f}C H:{humidity:.0f}%"
    else:
        line1 = f"S:{soil_percent}% W:{water_percent}%"

    write_text(pad_line(line1))


    # LCD rad 2
    status_messages = []

    if fan_on:
        status_messages.append("FAN ON")

    if pump_on:
        status_messages.append("PUMP ON")

    if water_percent <= MIN_WATER_LEVEL:
        status_messages.append("LOW WATER")

    if soil_percent < DRY_LIMIT:
        status_messages.append("SOIL DRY")

    if wifi_connected(status_messages):
        status_messages.append("Wifi connected")


    if len(status_messages) == 0:
        status_messages.append("SYSTEM OK")


    status_index = (
        time.ticks_ms() // 2000
    ) % len(status_messages)

    set_cursor(1, 0)

    line2 = status_messages[status_index]

    write_text(pad_line(line2))


    # MQTT
    now_ms = time.ticks_ms()

    if time.ticks_diff(
        now_ms,
        last_mqtt_publish
    ) >= MQTT_INTERVAL:

        data = {
            "temperature": temperature,
            "humidity": humidity,
            "soil_moisture": soil_percent,
            "water_level": water_percent,
            "fan_on": fan_on,
            "pump_on": pump_on
        }

        payload = json.dumps(data)

        # Om MQTT tappat anslutningen:
        # försök ansluta igen
        if mqtt_client is None and wifi_connected:
            mqtt_client = connect_mqtt()

        if mqtt_client is not None:
            try:
                mqtt_client.publish(
                    MQTT_TOPIC,
                    payload
                )

                print("MQTT published:", payload)

            except Exception as error:
                print("MQTT publish failed:", error)

                mqtt_client = None

        last_mqtt_publish = now_ms


    time.sleep(1)