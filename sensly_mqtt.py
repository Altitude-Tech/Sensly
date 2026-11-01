"""Publish Sensly HAT readings to Home Assistant over MQTT.

Uses Home Assistant MQTT discovery, so every reading appears automatically
as a sensor entity grouped under one "Sensly HAT" device. Nothing needs to
be added to Home Assistant's configuration.

Requires paho-mqtt:  sudo apt install python3-paho-mqtt
"""

import json
import socket
import sys
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    sys.exit("paho-mqtt is not installed. Run:  sudo apt install python3-paho-mqtt")


# key in the reading dict -> (friendly name, unit, device_class, state_class, icon, entity_category)
SENSORS = {
    'temperature': ('Temperature', '°C', 'temperature', 'measurement', None, None),
    'humidity': ('Humidity', '%', 'humidity', 'measurement', None, None),
    'pressure': ('Pressure', 'hPa', 'atmospheric_pressure', 'measurement', None, None),
    'co': ('Carbon Monoxide', 'ppm', 'carbon_monoxide', 'measurement', None, None),
    'co2': ('Carbon Dioxide', 'ppm', 'carbon_dioxide', 'measurement', None, None),
    'nh3': ('Ammonia', 'ppm', None, 'measurement', 'mdi:molecule', None),
    'methane': ('Methane', 'ppm', None, 'measurement', 'mdi:fire', None),
    'lpg': ('LPG', 'ppm', None, 'measurement', 'mdi:gas-cylinder', None),
    'propane': ('Propane', 'ppm', None, 'measurement', 'mdi:gas-cylinder', None),
    'hydrogen': ('Hydrogen', 'ppm', None, 'measurement', 'mdi:molecule', None),
    'methyl': ('Methyl', 'ppm', None, 'measurement', 'mdi:flask', None),
    'acetone': ('Acetone', 'ppm', None, 'measurement', 'mdi:flask', None),
    'pm10': ('PM10', 'µg/m³', 'pm10', 'measurement', None, None),
    'mq2_ratio': ('MQ2 RS/R0', None, None, 'measurement', 'mdi:ratio', 'diagnostic'),
    'mq7_ratio': ('MQ7 RS/R0', None, None, 'measurement', 'mdi:ratio', 'diagnostic'),
    'mq135_ratio': ('MQ135 RS/R0', None, None, 'measurement', 'mdi:ratio', 'diagnostic'),
}


def _make_client(client_id):
    """Create a paho client that works with both paho-mqtt 1.x and 2.x."""
    if hasattr(mqtt, 'CallbackAPIVersion'):
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                           protocol=mqtt.MQTTv311)
    return mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)


class SenslyMQTT:

    def __init__(self, config):
        self.config = config
        self.device_id = config['device_id']
        self.state_topic = 'sensly/%s/state' % self.device_id
        self.availability_topic = 'sensly/%s/status' % self.device_id
        self.client = _make_client('sensly-%s' % socket.gethostname())
        if config.get('username'):
            self.client.username_pw_set(config['username'], config.get('password'))
        self.client.will_set(self.availability_topic, 'offline', retain=True)
        self.client.on_connect = self._on_connect
        self._discovery_sent = False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        # paho 1.x passes an int rc, 2.x passes a ReasonCode object
        ok = (reason_code == 0) if isinstance(reason_code, int) else (not reason_code.is_failure)
        if not ok:
            print("MQTT connection refused: %s (check username/password in sensly.conf)"
                  % reason_code, flush=True)
            return
        print("Connected to MQTT broker %s:%d" % (self.config['host'], self.config['port']), flush=True)
        # (Re)send discovery on every connect so HA re-creates entities if it restarted
        self._send_discovery()
        client.publish(self.availability_topic, 'online', retain=True)

    def connect(self):
        try:
            self.client.connect(self.config['host'], self.config['port'], keepalive=60)
        except (OSError, socket.gaierror) as exc:
            sys.exit("Could not reach MQTT broker %s:%d (%s).\n"
                     "Check the host in sensly.conf and that the Mosquitto add-on is running."
                     % (self.config['host'], self.config['port'], exc))
        self.client.loop_start()
        # Give the connection a moment so the first publish is not lost
        for _ in range(50):
            if self.client.is_connected():
                break
            time.sleep(0.1)

    def _send_discovery(self):
        device = {
            'identifiers': [self.device_id],
            'name': self.config['device_name'],
            'manufacturer': 'Altitude Technology',
            'model': 'Sensly HAT v1.1',
        }
        prefix = self.config['discovery_prefix']
        for key, (name, unit, device_class, state_class, icon, category) in SENSORS.items():
            payload = {
                'name': name,
                'unique_id': '%s_%s' % (self.device_id, key),
                'object_id': '%s_%s' % (self.device_id, key),
                'state_topic': self.state_topic,
                'value_template': '{{ value_json.%s }}' % key,
                'availability_topic': self.availability_topic,
                'device': device,
                'expire_after': 600,
            }
            if unit:
                payload['unit_of_measurement'] = unit
            if device_class:
                payload['device_class'] = device_class
            if state_class:
                payload['state_class'] = state_class
            if icon:
                payload['icon'] = icon
            if category:
                payload['entity_category'] = category
            topic = '%s/sensor/%s/%s/config' % (prefix, self.device_id, key)
            self.client.publish(topic, json.dumps(payload), retain=True)
        self._discovery_sent = True

    def publish(self, reading):
        self.client.publish(self.state_topic, json.dumps(reading))

    def close(self):
        try:
            self.client.publish(self.availability_topic, 'offline', retain=True)
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
