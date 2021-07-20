
from network import WLAN
from machine import UART
import machine
import os
import config
import pycom
import time

uart = UART(0, baudrate=115200)
os.dupterm(uart)

# RGBLED
# Disable the on-board heartbeat
pycom.heartbeat(False)
time.sleep(0.1)
pycom.rgbled(0xff0000)  # Status red = not working

# Connecting to WiFi
wlan = WLAN() # get current object, without changing the mode

if machine.reset_cause() != machine.SOFT_RESET:
    wlan.init(mode=WLAN.STA)


if not wlan.isconnected():
    wlan.connect(config.WIFI_SSID, auth=(WLAN.WPA2, config.WIFI_PASS))
    while not wlan.isconnected():
        machine.idle() # save power while waiting

print("Connected to Wifi")
pycom.rgbled(0xffd7000) # Status orange: partially working
print(wlan.ifconfig())
machine.main('main.py')
