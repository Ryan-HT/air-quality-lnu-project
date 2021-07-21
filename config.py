# Wireless network
WIFI_SSID = "<YOUR_WIFI_SSID>"
WIFI_PASS = "<YOUR_WIFI_PASSWORD>"


# MQTT serer's configuration
MQTT_SERVER = "<YOUR_MQTT_SERVER_IP"
MQTT_PORT = 1883
MQTT_USER = "<MQTT_USER_NAME"
MQTT_KEY = "<MQTT_PASSWORD>"
MQTT_CLIENT_ID = "id-1223"  # Can be anything start with id- 
MQTT_TEMPERATURE_FEED = "devices/temperature"
MQTT_HUMIDITY_FEED = "devices/humidity"
MQTT_POLLUTANT_FEED = "devices/pollutant"

#SSL
SSL_FILES = dict([
    ("ca_certs", "/flash/cert/CA.pem"),
    ("keyfile", "/flash/cert/client-key.pem"),
    ("certfile", "/flash/cert/clent-cert.pem")
])

# Other variables
WDT_TIMEOUT = const(600000)
