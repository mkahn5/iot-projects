#!/usr/bin/python

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function
import datetime
import argparse
import json
import time

from time import sleep
from pytz import timezone
import pytz

import jwt
import paho.mqtt.client as mqtt

from Adafruit_BME280 import *
import RPi.GPIO as GPIO

FAN_GPIO = 21
sensor = BME280(t_mode=BME280_OSAMPLE_8, p_mode=BME280_OSAMPLE_8,
                h_mode=BME280_OSAMPLE_8)

# Update and publish temperature readings at a rate of SENSOR_POLL amount seconds
SENSOR_POLL = 120


def create_jwt(project_id, private_key_file, algorithm):
    """Create a JWT (https://jwt.io) to establish an MQTT connection."""
    token = {
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
        'aud': project_id
    }
    with open(private_key_file, 'r') as f:
        private_key = f.read()
    print('Creating JWT using {} from private key file {}'.format(algorithm, private_key_file))
    return jwt.encode(token, private_key, algorithm=algorithm)


def exit_handler():
    GPIO.output(12, GPIO.LOW)


def error_str(rc):
    """Convert a Paho error to a human readable string."""
    return '{}: {}'.format(rc, mqtt.error_string(rc))


class Device(object):
    """Represents the state of a single device."""

    def __init__(self):
        self.temperature = 0
        self.fan_on = False
        self.connected = False

    def update_sensor_data(self):
        self.temperature = int(sensor.read_temperature())

    #  def read_temperature_f(self):
    # Wrapper to get temp in F
    #    celsius = self.read_temperature()
    #    temp = celsius * 1.8 + 32
    #    return temp

    def wait_for_connection(self, timeout):
        """Wait for the device to become connected."""
        total_time = 0
        while not self.connected and total_time < timeout:
            time.sleep(1)
            total_time += 1

        if not self.connected:
            raise RuntimeError('Could not connect to MQTT bridge.')

    def on_connect(self, unused_client, unused_userdata, unused_flags, rc):
        """Callback for when a device connects."""
        print('Connection Result:', error_str(rc))
        self.connected = True

    def on_disconnect(self, unused_client, unused_userdata, rc):
        """Callback for when a device disconnects."""
        print('Disconnected:', error_str(rc))
        self.connected = False
        GPIO.output(12, GPIO.LOW)

    def on_publish(self, unused_client, unused_userdata, unused_mid):
        """Callback when the device receives a PUBACK from the MQTT bridge."""
        print('Published message acked, sleeping 120 sec')

    def on_subscribe(self, unused_client, unused_userdata, unused_mid,
                     granted_qos):
        """Callback when the device receives a SUBACK from the MQTT bridge."""
        print('Subscribed: ', granted_qos)
        if granted_qos[0] == 128:
            print('Subscription failed.')

    def on_message(self, unused_client, unused_userdata, message):
        """Callback when the device receives a message on a subscription."""
        payload = str(message.payload)
        print("Received message '{}' on topic '{}' with Qos {}".format(payload, message.topic, str(message.qos)))

        # The device will receive its latest config when it subscribes to the config
        # topic. If there is no configuration for the device, the device will
        # receive an config with an empty payload.
        if not payload:
            return

        # The config is passed in the payload of the message. In this example, the
        # server sends a serialized JSON string.
        data = json.loads(payload)
        if data['fan_on'] != self.fan_on:
            # If we're changing the state of the fan, print a message and update our
            # internal state.
            self.fan_on = data['fan_on']
            if self.fan_on:
                GPIO.output(FAN_GPIO, GPIO.HIGH)
                print('Fan turned on.')
            else:
                GPIO.output(FAN_GPIO, GPIO.LOW)
                print('Fan turned off.')


def parse_command_line_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Example Google Cloud IoT MQTT device connection code.')
    parser.add_argument(
        '--project_id', required=True, help='GCP cloud project name')
    parser.add_argument(
        '--registry_id', required=True, help='Cloud IoT registry id')
    parser.add_argument('--device_id', required=True,
                        help='Cloud IoT device id')
    parser.add_argument(
        '--private_key_file', required=True, help='Path to private key file.')
    parser.add_argument(
        '--algorithm',
        choices=('RS256', 'ES256'),
        required=True,
        help='Which encryption algorithm to use to generate the JWT.')
    parser.add_argument(
        '--cloud_region', default='us-central1', help='GCP cloud region')
    parser.add_argument(
        '--ca_certs',
        default='roots.pem',
        help='CA root certificate. Get from https://pki.google.com/roots.pem')
    parser.add_argument(
        '--num_messages',
        type=int,
        default=100,
        help='Number of messages to publish.')
    parser.add_argument(
        '--mqtt_bridge_hostname',
        default='mqtt.googleapis.com',
        help='MQTT bridge hostname.')
    parser.add_argument(
        '--mqtt_bridge_port', default=8883, help='MQTT bridge port.')

    return parser.parse_args()


# start get client
def get_client(
        device, project_id, cloud_region, registry_id, device_id, private_key_file,
        algorithm, ca_certs, mqtt_bridge_hostname, mqtt_bridge_port):
    """Create our MQTT client. The client_id is a unique string that identifies
     this device. For Google Cloud IoT Core, it must be in the format below."""
    client = mqtt.Client(
        client_id=('projects/{}/locations/{}/registries/{}/devices/{}'
            .format(
            project_id,
            cloud_region,
            registry_id,
            device_id)))

    # With Google Cloud IoT Core, the username field is ignored, and the
    # password field is used to transmit a JWT to authorize the device.
    client.username_pw_set(
        username='unused',
        password=create_jwt(
            project_id, private_key_file, algorithm))

    # Enable SSL/TLS support.
    client.tls_set(ca_certs=ca_certs)

    # Register message callbacks. https://eclipse.org/paho/clients/python/docs/
    # describes additional callbacks that Paho supports. In this example, the
    # callbacks just print to standard out.
    #     client.on_connect = on_connect
    client.on_connect = device.on_connect
    client.on_publish = device.on_publish
    client.on_disconnect = device.on_disconnect
    client.on_subscribe = device.on_subscribe
    client.on_message = device.on_message
    # Connect to the Google MQTT bridge.
    client.connect(mqtt_bridge_hostname, mqtt_bridge_port)
    # Start the network loop.
    return client


def main():
    while True:
        args = parse_command_line_args()
        # Setup GPIOs for the RasPi3 and cobbler
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(FAN_GPIO, GPIO.OUT)
        device = Device()

        jwt_exp_mins = 20

        # This is the topic that the device will publish telemetry events (temperature
        # data) to.
        mqtt_telemetry_topic = '/devices/{}/events'.format(args.device_id)

        # This is the topic that the device will receive configuration updates on.
        mqtt_config_topic = '/devices/{}/config'.format(args.device_id)

        jwt_iat = datetime.datetime.utcnow()
        client = get_client(
            device, args.project_id, args.cloud_region,
            args.registry_id, args.device_id, args.private_key_file,
            args.algorithm, args.ca_certs, args.mqtt_bridge_hostname,
            args.mqtt_bridge_port)
        client.loop_start()
        # Wait up to 5 seconds for the device to connect.
        device.wait_for_connection(5)

        client.subscribe(mqtt_config_topic, qos=1)


        # Update and publish temperature readings at a rate of one per second.
        for _ in range(args.num_messages):

            seconds_since_issue = (datetime.datetime.utcnow() - jwt_iat).seconds
            if seconds_since_issue > 60 * jwt_exp_mins:
                print('Refreshing token after {}s'.format(seconds_since_issue))
                client.loop_stop()
                jwt_iat = datetime.datetime.utcnow()
                client = get_client(
                    device, args.project_id, args.cloud_region,
                    args.registry_id, args.device_id, args.private_key_file,
                    args.algorithm, args.ca_certs, args.mqtt_bridge_hostname,
                    args.mqtt_bridge_port)
                client.loop_start()
                # Wait up to 5 seconds for the device to connect.
                device.wait_for_connection(5)

                client.subscribe(mqtt_config_topic, qos=1)
            device.update_sensor_data()

            # Report the device's temperature to the server, by serializing it as a JSON
            # string.
            #    payload = json.dumps({'temperature': device.temperature})
            #    time = datetime.utcnow()

            #  utc to pst conversion
            #    date_format='%m/%d/%Y %H:%M:%S %Z'
            date_format = '%Y-%m-%d %H:%M'
            date = datetime.datetime.now(tz=pytz.utc)
            date = date.astimezone(timezone('US/Pacific'))

            now = datetime.datetime.now()
            temp = float(device.temperature) * 1.8 + 32
            #    data = {'temp' : temp, 'time' : now.strftime("%Y-%m-%d %H:%M")}
            data = {'temperature': temp,
                    'timestamp': date.strftime(date_format)}

            #    payload = json.dumps({'temperature': temp})
            #    payload2 = json.dumps({'time': now.strftime("%Y-%m-%d %H:%M")})
            payload3 = json.dumps(data)
            print('Publishing payload', payload3)
            # turn on greenlight to confirm transmitting data
            GPIO.setup(12, GPIO.OUT)
            GPIO.output(12, GPIO.HIGH)
            if temp <= 67:
                GPIO.setup(21, GPIO.OUT)
                GPIO.output(21, GPIO.HIGH)
            #   time.sleep(1)
            else:
                GPIO.output(21, GPIO.LOW)
            client.publish(mqtt_telemetry_topic, payload3, qos=1)
            time.sleep(SENSOR_POLL)

        client.disconnect()

        client.loop_stop()
        GPIO.setmode(GPIO.BCM)
        GPIO.output(12, GPIO.LOW)

        GPIO.cleanup()


#  print 'Finished loop successfully. Goodbye!'

if __name__ == '__main__':
    main()
