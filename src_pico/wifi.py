import json 
import network
import rp2
import time

rp2.country("SE")

with open("wifi_credentials.json") as file:
    credentials = json.load(file)

def connect_wifi(waiting_time = 30):
    # pico becomes a client to connect to WIFI
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True) # powers on radio WIFI on pico W/2W
    wlan.connect(credentials.get("SSID"), credentials.get("PASSWORD"))

    while waiting_time > 0:
        if wlan.isconnected():
            print("Wifi connected")
            print("IP:", wlan.ifconfig())
            break

        waiting_time -= 1
        print("Trying to connect to wifi...")
        print("WiFi status:", wlan.status())
        time.sleep(2)

    return wlan.isconnected()

