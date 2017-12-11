# Raspberry Pi Temp Monitor with Google Cloud IoT
This script authenticates to Google Cloud IoT and publishes temperatature from a BME280 sensor with a timestamp to the PubSub topic setup for the Cloud IoT device.

If the temperature is less than or equal to 67 degrees, the Raspberry Pi GPIO pin 21 will light blue.
When the script is sucessfully publishing to Cloud IoT and PubSub, GPIO pin 21 will light green. When the script is not working the light will not display.

To run:
```
python pubsub_thermostat_f8.py --project_id=<your gcp project> --registry_id=<your gcp cloud iot registryid> --device_id=<device name> --private_key_file=rsa_private.pem --algorithm=RS256
```

Dataflow pipeline included to parse data from PubSub to Datastore and BigQuery.
