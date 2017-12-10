# IoT Projects

## Raspberry Pi Temp Notification with Google Cloud IoT
This script authenticates to Google Cloud IoT with JWTs and MQTT and publishes temperatature from a BME280 sensor with a timestamp to the PubSub topic setup for the Cloud IoT device.

If the temperature is less than or equal to 67 degrees, the Raspberry Pi GPIO pin 21 will light blue.
When the script is sucessfully publishing to Cloud IoT and PubSub, GPIO pin 21 will light green. When the script is not working the light will not display.

