import paho.mqtt.client as mqtt
import json

STATE_TOPIC = 'pharmaceutical_warehouse/manipulator_state'
LOGS_TOPIC = 'pharmaceutical_warehouse/manipulator_logs'
BROKER = 'broker.hivemq.com'
PORT = 1883

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print("Successfully connected to MQTT broker")
    else:
        print(f"Failed to connect. Code: {rc}")

client.on_connect = on_connect

try:
    client.connect(BROKER, PORT, 60)
    client.loop_start()
except Exception as e:
    print(f"MQTT initialization failed: {e}")

def publish_manipulator_state(status, position=None, current_operation=None):
    try:
        payload = {
            "status": status,
            "position": str(position) if position else None,
            "current_operation": current_operation
        }
        client.publish(STATE_TOPIC, json.dumps(payload))
    except Exception as e:
        print(f"Failed to publish manipulator state: {e}")

def publish_new_log(log_dict):
    try:
        client.publish(LOGS_TOPIC, json.dumps(log_dict))
    except Exception as e:
        print(f"Failed to publish new log: {e}")
