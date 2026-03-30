from mongoengine import Document, StringField, DateTimeField, IntField, ReferenceField
from apps.storage_location.models import StorageLocation
from apps.products.models import Product
from datetime import datetime
from zoneinfo import ZoneInfo

def get_ua_time():
    return datetime.now(ZoneInfo("Europe/Kyiv"))

class RoboArmOperationsLog(Document):
    timestamp = DateTimeField(default=get_ua_time)

    operation_types_list = ["PICK", "PUT", "MOVE", "STOP", "START"]
    operation_type = StringField(required=True, choices=operation_types_list)

    operation_status_list = ["SUCCESS", "FAILURE", "ABORTED"]
    operation_status = StringField(default='SUCCESS', required=True, choices=operation_status_list)
    
    location = ReferenceField(StorageLocation, null=True)
    product = ReferenceField(Product, null=True)

    duration_ms = IntField(required=True)
    error_msg = StringField(null=True)

    meta = {'collection': 'tech_logs'}