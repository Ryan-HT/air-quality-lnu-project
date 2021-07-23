import pycom
import os
import socket
import time
import struct
import machine
from network import LoRa
from uos import urandom
from machine import Pin
from machine import I2C
from dht import DHT                 # https://github.com/JurassicPork/DHT_PyCom
import CCS811                       # https://gist.github.com/jiemde

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

# Use different device id for each device or a dictionary to save ID/lastMessageID
# This device ID,
_DEVICE_ID = 0x01
_MAX_ACK_TIME = 5000
_RETRY_COUNT = 3


i2c = I2C(0, pins=('P9','P10'))      # PIN assignments (P9=SDA, P10=SCL)
i2c.init(I2C.MASTER, baudrate=10000) # init as a master


pycom.heartbeat(False)              # Turn of heartbeat
pycom.rgbled(0x000008)              # blue
CCS811_ADDR = const(0x5A)           # CCS811 Address
ccs = CCS811.CCS811(i2c=i2c, addr=CCS811_ADDR)  # CCS811 initialization
indoorDHT = DHT(Pin('P3', mode=Pin.OPEN_DRAIN),1)      # DHT22 initialization
outdoorDHT = DHT(Pin('P4', mode=Pin.OPEN_DRAIN),0)     # DHT11 initialization
time.sleep(2) # Just to get it some slack starting up ...
numberOfReading = indoorTemp = indoorHumidity = outdoorTemp = outdoorHumidity = eCO2 = tVOC = 0

# Open a Lora Socket, use tx_iq to avoid listening to our own messages
# Please pick the region that matches where you are using the device:
# Asia = LoRa.AS923
# Australia = LoRa.AU915
# Europe = LoRa.EU868
# United States = LoRa.US915
lora = LoRa(mode=LoRa.LORA, tx_iq=True, region=LoRa.EU868)
lora_sock = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
lora_sock.setblocking(False)

# Method to increase message id and keep in between 1 and 255
msg_id = 0
def random_msg_id():
    global msg_id
    msg_id = machine.rng() & 0xFF
random_msg_id()
# Method for acknoledge waiting time keep
def check_ack_time(from_time):
    current_time = time.ticks_ms()
    return (current_time - from_time > _MAX_ACK_TIME)

# Method to send messages
def send_msg(indoorTemp, indoorHumid, outdoorTemp, outdoorHumid, eco2, etvoc):
    global msg_id
    retry = _RETRY_COUNT
    while (retry > 0 and not retry == -1):
        retry -= 1
        pkg = struct.pack(_LORA_PKG_FORMAT, _DEVICE_ID, msg_id, indoorTemp, indoorHumid, outdoorTemp, outdoorHumid, eco2, etvoc)
        print('Send message id %d' % msg_id)
        lora_sock.send(pkg)

        # Wait for the response from the server.
        start_time = time.ticks_ms()

        while(not check_ack_time(start_time)):
            #print("RECV_ACK")
            recv_ack = lora_sock.recv(256)
            # If a message of the size of the acknoledge message is received
            if (len(recv_ack) == 3):
                print("ACK SIZE CORRECT")
                device_id, recv_msg_id, status = struct.unpack(_LORA_PKG_ACK_FORMAT, recv_ack)
                if (device_id == _DEVICE_ID and recv_msg_id == msg_id):
                    if (status == 200):
                        # Do some code if your message arrived at the central
                        return True
                    else:
                        return False
        time.sleep_ms(urandom(1)[0] << 2)
    return False

# START READING FROM SENSORS AND SENDING

# Do Reading Ten (10) Times
while numberOfReading < 10:
    ## Start Sensor Readings
    indoor = indoorDHT.read()
    outdoor = outdoorDHT.read()
    if indoor.is_valid() and outdoor.is_valid() and ccs.data_available():
        numberOfReading += 1
        pycom.rgbled(0x001000) # green
        ccs.put_envdata(humidity=indoor.humidity,temp=indoor.temperature)   # Compensate Temp/Humidity Error
        indoorTemp += indoor.temperature
        indoorHumidity += indoor.humidity
        outdoorTemp += outdoor.temperature
        outdoorHumidity += outdoor.humidity
        print('Indoor Temperature: {:3.2f}'.format(indoor.temperature/1.0))
        print('Insoor Humidity: {:3.2f}'.format(indoor.humidity/1.0))
        print("Outdoor Temperature: %d C" % outdoor.temperature)
        print("Outdoor Humidity: %d %%" % outdoor.humidity)
        co2 = ccs.eCO2
        voc = ccs.tVOC
        eCO2 += ccs.eCO2
        tVOC += ccs.tVOC
        #if co2 > 10:
        print('CO2 level: {}{} '.format(str(co2), ' ppm  '), end='')
        print('tVOC level: {}'.format(str(voc)))
    else:
        pycom.rgbled(0xFF0000) # read
    ## End Sensor Readings
    #machine.deepsleep(1000*60) #sleep for 1 minute
    #print("Wake Up from sleep")
    time.sleep(2)

print('Indoor Temp is: ', indoorTemp/10.0)
print('Outdoor Temp is: ', outdoorTemp/10.0)
print('Indoor Humidity is: ', indoorHumidity/10.0)
print('Outdoor Humidity is: ', outdoorHumidity/10.0)
print('CO2 is: ', eCO2/10.0)
print('tVOC is: ', tVOC/10.0)


"""
The equivalent CO2 (eCO2) output range for CCS811 is from 400ppm to 8192ppm.
Values outside this range are clipped. The Total Volatile Organic Compound (TVOC)
output range for CCS811 is from 0ppb to 1187ppb. Values outside this range are
clipped.
"""


# BBFFFFFF = 1 + 1 + 4 + 4 + 4 + 4 + 4 + 4 = 16 ==> look above for description
# It sends the average of 10 reading
success = send_msg(indoorTemp/10.0, outdoorTemp/10.0, indoorHumidity/10.0, outdoorHumidity/10.0, eCO2/10.0, tVOC/10.0)
if (success):
	# The following line borrowed from another project
	# If the uart = machine.UART(0, 115200) and os.dupterm(uart) are set in the boot.py this print should appear in the serial port
    print("ACK RECEIVED: %d" % msg_id)
    # If sensor could send the message successfully then goes to sleep for 5 minutes
    machine.deepsleep(1000*60*5)
else:
    # The following line borrowed from another project
	# If the uart = machine.UART(0, 115200) and os.dupterm(uart) are set in the boot.py this print should appear in the serial port
    print("MESSAGE FAILED")
    # If sensor could not send the message successfully goes to sleep for 1 minute
    machine.deepsleep(1000*60)
    # Manage the error message
