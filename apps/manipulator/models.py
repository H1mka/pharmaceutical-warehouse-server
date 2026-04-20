from mongoengine import Document, StringField, DateTimeField, IntField, ReferenceField
from apps.storage_location.models import StorageLocation
from apps.products.models import Product
from datetime import datetime
from zoneinfo import ZoneInfo

def get_ua_time():
    return datetime.now(ZoneInfo("Europe/Kyiv"))

class ManipulatorLog(Document):
    timestamp = DateTimeField(default=get_ua_time)
    max_attempts = 2

    operation_status_list = ["SUCCESS", "FAILURE", "ABORTED"]
    operation_status = StringField(default='SUCCESS', required=True, choices=operation_status_list)

    operation_types_list = ["PICK", "PUT", "MOVE", "STOP", "START"]
    operation_type = StringField(required=True, choices=operation_types_list)
    
    duration_ms = IntField(required=True)
    attempt = IntField(required=True)

    storage_location = ReferenceField(StorageLocation, null=True)
    product = ReferenceField(Product, null=True)

    error_msg = StringField(null=True)

    meta = {'collection': 'logs.manipulator',
            'indexes': [
                '-timestamp', 
            ]
    }