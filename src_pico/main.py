from dht import DHT11 # ändra till DHT11 under hardware
from machine import Pin, I2C, ADC
from neopixel import NeoPixel
from wifi import connect_wifi
from umqtt.simple import MQTTClient

import time
import json

# MQTT
TOPIC = b"greenhouse"
# Ändra till IPv4-adressen för datorn där Mosquitto körs
MQTT_BROKER = "192.168.1.95"

def connect_mqtt():
    client = MQTTClient(client_id="pico", server = MQTT_BROKER, port=1883)
    client.connect()
    print("Connected to MQTT")
    return client

# DHT22 / ändra till DHT11 under hardware
sensor = DHT11(Pin(16))

# WS2812 (RGB Strip)
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


def clear_lcd():
    command(0x01)
    time.sleep_ms(2)

# För LCD
def pad_line(text):
    text = str(text)

    if len(text) < 16:
        text += " " * (16 - len(text))

    return text[:16]

# Fan
fan_led = Pin(14, Pin.OUT)

HIGH_TEMP = 30
LOW_TEMP = 28
HOT_TIME_REQUIRED = 5

hot_since = None
fan_on = False

# Pump
soil_sensor = ADC(26) # För att simulera jordfuktighet
water_sensor = ADC(27) # För att simulera mängden vatten i pumpen

# Jordfuktighet
pump_led = Pin(13, Pin.OUT)

DRY_LIMIT = 30
WET_LIMIT = 45
DRY_TIME_REQUIRED = 5

dry_since = None
pump_on = False

# Vatten i pump
MIN_WATER_LEVEL = 20


# Start LCD
lcd_init()

# Wifi status på LCD
set_cursor(0, 0)
write_text(pad_line("Connecting WiFi"))

set_cursor(1, 0)
write_text(pad_line("Please wait..."))

wifi_connected = connect_wifi()

# MQTT-client skapas först efter WiFi
client = None

if wifi_connected:
    set_cursor(0, 0)
    write_text(pad_line("WiFi connected"))

    set_cursor(1, 0)
    write_text(pad_line("SYSTEM STARTING"))

    time.sleep(2)

else:
    set_cursor(0, 0)
    write_text(pad_line("WiFi failed"))

    set_cursor(1, 0)
    write_text(pad_line("EDGE MODE"))

    time.sleep(2)


# Main loop
while True:

    # Läs Sensorer
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

    # Fläktlogik
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

    #MQTT data
    data = {
    "temperature": temperature,
    "humidity": humidity,
    "soil_moisture": soil_percent,
    "water_level": water_percent,
    "fan_on": fan_on,
    "pump_on": pump_on
    }

    payload = json.dumps(data)

    if client is not None:
        try:
            client.publish(TOPIC, payload)
            print("Published:", payload)
        except Exception as error:
            print("MQTT publish failed:")
            print(error)
            
    # LCD
    display_page = (time.ticks_ms() // 2000) % 2

    # Rad 1
    set_cursor(0, 0)

    if display_page == 0:
        line1 = f"T:{temperature:.1f}C H:{humidity:.0f}%"
    else:
        line1 = f"S:{soil_percent}% W:{water_percent}%"

    write_text(pad_line(line1))


    # Rad 2
    status_messages = []

    if fan_on:
        status_messages.append("FAN ON")

    if pump_on:
        status_messages.append("PUMP ON")

    if water_percent <= MIN_WATER_LEVEL:
        status_messages.append("LOW WATER")

    if soil_percent < DRY_LIMIT:
        status_messages.append("SOIL DRY")

    if len(status_messages) == 0:
        status_messages.append("SYSTEM OK")

    status_index = (time.ticks_ms() // 2000) % len(status_messages)

    set_cursor(1, 0)

    line2 = status_messages[status_index]
    write_text(pad_line(line2))

    time.sleep(1)