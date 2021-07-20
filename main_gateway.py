"""
This file is the main.py for the gateway in our system that do:
1. Receive LoRa message from node(s) check the format and send the aknowledgement
   once it find a unique message (check node & message ID for specific message) from a node.
2. Then it put node message in three different category; temperature, humidity and
   pullution and publish them to the corresponding topics in MQTT server.
Node: We try to catch some of the possible crash causes but still may need more
      adjustment to capture all of them.
"""
import socket                 # For LoRa socket
import struct                 # Packing and Unpacking LoRa packages
from network import LoRa      # LoRa connectivity
from network import WLAN      # For operation of WiFi network (Disconnecting)
import time                   # Allows use of time.sleep() for delays
import pycom                  # Base library for Pycom devices
from mqtt import MQTTClient   # For use of MQTT protocol to talk to MQTT server
import ubinascii              # Needed to run any MicroPython code
import machine                # Interfaces with hardware components
import micropython            # Needed to run any MicroPython code
import config                 # Config.py holding user credential and constants
import ujson                  # Creating JSON object for MQTT & Telegraf
from machine import WDT       # Watchdog Timer to reset the board when stuck
import sys                    # Using sys to print Exception reasons
import _thread

# BEGIN SETTINGS
# Initializing Watchdog Timer to active after 10 minutes
watchdog = WDT(timeout=config.WDT_TIMEOUT)

# The package header
# B: 1 byte for the deviceId
# B: 1 byte for the lastMessageRandomId
# f: 4 bytes for the indoorTemperature
# f: 4 bytes for the indoorHumidity
# f: 4 bytes for the outdoorTemperature
# f: 4 bytes for the outdoorHumidity
# f: 4 bytes for the eCO2
# f: 4 bytes for the eTVOC
_LORA_PKG_FORMAT = "!BBffffff"

# The ack package
# B: 1 byte for the deviceId
# B: 1 byte for the lastMessageRandomId
# B: 1 byte for the Ok (200) or error messages
_LORA_PKG_ACK_FORMAT = "BBB"


lora = None
lora_sock = None
# END SETTINGS

def start_lora():
    global lora
    global lora_sock

	# Open a Lora Socket, use rx_iq to avoid listening to our own messages
    # Please pick the region that matches where you are using the device:
    # Asia = LoRa.AS923
    # Australia = LoRa.AU915
    # Europe = LoRa.EU868
    # United States = LoRa.US915
    print("Init LoRa radio...", end='')
    lora = LoRa(mode=LoRa.LORA, rx_iq=True, region=LoRa.EU868)
    print("Done!!!")
    print("Init LoRa socket...", end='')
    lora_sock = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    print("Done!!!")
    print("Disable LoRa blocking...", end='')
    lora_sock.setblocking(False)
    print("Done!!!")
    print('Gateway started...')
    print("Ready to receive LoRa packets")

def build_json(variable_1, value_1, variable_2, value_2):
    try:
        data = {variable_1: value_1, variable_2: value_2}
        retValue = ujson.dumps(data)
        return retValue
    except:
        return None

def send_topic(topicObject, topicName):
    print(topicObject)
    try:
        client.publish(topic=topicName, msg=topicObject)
        watchdog.feed()
        print("DONE")
    except Exception as e:
        print("FAILED")
        # We must add error hadling here if WiFi being unavailable here


def pub_sensor_values(indoorTemperature, outdoorTemperature, indoorHumidity, outdoorHumidity, co2, tvoc):
    pycom.rgbled(0x00ff00) # Status green: online to Adafruit IO

    try:
        tempObj = build_json("indoorTemp", indoorTemperature, "outdoorTemp", outdoorTemperature)
        send_topic(tempObj, config.MQTT_TEMPERATURE_FEED)
        humidObj = build_json("indoorHumid", indoorHumidity, "outdoorHumid", outdoorHumidity)
        send_topic(humidObj, config.MQTT_HUMIDITY_FEED)
        polluObj = build_json("co2", co2, "tvoc", tvoc)
        send_topic(polluObj, config.MQTT_POLLUTANT_FEED)
    except:
        print("MQTT Brocker does not work")
        client.disconnect()   # ... disconnect the client and clean up.
        client = None
        wlan.disconnect()
        wlan = None
        pycom.rgbled(0x000022) # Status blue: stopped
        print("Disconnected from MQTT server.")





def listen_to_lora():
    last_msg_id = -1    # Initialization of last_messge_id for ignoring duplicate message from Node
    while (True):

        # Since the maximum body size in the protocol is 255 the request is limited to 512 bytes
        recv_pkg = lora_sock.recv(512)

        # We must measure the exact size of correct package at development otherwise
        # The server will crash so here we can measure what is the correct size
        # and base on that tell which packet to process
        #print(len(recv_pkg))


        # If at least a message with the header is received process it
        # Nodes sends 26 bytes in each packet so here we only react to those
        # Look above ==> BBFFFFFF = 1 + 1 + 4 + 4 + 4 + 4 + 4 + 4 = 26
        if len(recv_pkg) == 26:
            print("Package received")
            print(recv_pkg)

            try:
                # Unpack the message based on the protocol definition
                device_id, msg_id, indoorTemp, outdoorTemp, indoorHumid, outdoorHumid, eco2, etvoc = struct.unpack(_LORA_PKG_FORMAT, recv_pkg)
            except:
                # If the size of the message is correct but format does not match, Then
                # ignore the message (maybe some other network send you message with
                # same size)
                continue

            # Currently we hard code device_id but we can save device_id in a dictionary for several clients
            if device_id == 0x01 and last_msg_id == msg_id:
                continue    # if server already got the message, ignore it.
            last_msg_id = msg_id

            print('Printing received value for debugging...:')
            print('Indoor temp is: ', indoorTemp)
            print('Indoor humidity is: ', indoorHumid)
            print('Outdoor temp is: ', outdoorTemp)
            print('Outdoor humidity is: ', outdoorHumid)
            print('eco2 is: ', eco2)
            print('etvoc is: ', etvoc)

            # Respond to the device with an acknoledge package
            # time.sleep(0.15)
            ack_pkg = struct.pack(_LORA_PKG_ACK_FORMAT, device_id, msg_id, 200)
            lora_sock.send(ack_pkg)
            print("sent ack")

            # Publish the message to MQTT server
            _thread.start_new_thread(pub_sensor_values, [indoorTemp, outdoorTemp, indoorHumid, outdoorHumid, eco2, etvoc])

        time.sleep(0.2)

# Handle buffer Exception
micropython.alloc_emergency_exception_buf(100)

# Initializing LoRa for the Gateway
start_lora()
time.sleep(1)

# Initializing and Connecting to MQTT server
try:
    client = MQTTClient(client_id=config.MQTT_CLIENT_ID, server=config.MQTT_SERVER, port=config.MQTT_PORT, user=config.MQTT_USER, password=config.MQTT_KEY)
    time.sleep(0.1)
    client.connect()
    print("Connected to %s" % (config.MQTT_SERVER))
except Exception as error:
    sys.print_exception(error, sys.stderr)
    print("Could not establish MQTT connection")
    wlan.disconnect()
    wlan = None
    pycom.rgbled(0x000022)  # Status blue: stopped
    print("Disconnected from WiFi.")
    # sleep for 20 second and reset the board
    machine.deepsleep(1000*20)


_thread.start_new_thread(listen_to_lora, [])

pycom.rgbled(0x00ff00) # Status green: online to ready to receive messages
