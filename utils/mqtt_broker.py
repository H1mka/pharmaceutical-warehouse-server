import json

from django.conf import settings
from django.utils import timezone


def publish_product_update(event, product=None, extra=None):
    payload = {
        "event": event,
        "product": product,
        "extra": extra or {},
        "created_at": timezone.now().isoformat(),
    }

    try:
        import paho.mqtt.publish as mqtt_publish

        mqtt_publish.single(
            settings.MQTT_PRODUCT_UPDATES_TOPIC,
            payload=json.dumps(payload),
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            client_id=settings.MQTT_CLIENT_ID,
            keepalive=settings.MQTT_KEEPALIVE,
            qos=settings.MQTT_QOS,
            retain=False,
        )
    except Exception as exc:
        return {
            "published": False,
            "topic": settings.MQTT_PRODUCT_UPDATES_TOPIC,
            "error": str(exc),
        }

    return {
        "published": True,
        "topic": settings.MQTT_PRODUCT_UPDATES_TOPIC,
        "payload": payload,
    }


def publish_product_received(product, quantity):
    return publish_product_update(
        "PRODUCT_RECEIVED",
        {
            "id": str(product.id),
            "sku": product.sku,
            "name": product.name,
        },
        {"quantity_delta": quantity},
    )
