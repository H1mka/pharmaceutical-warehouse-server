import datetime
from mongoengine import Document, StringField, DateTimeField, IntField, ReferenceField

from apps.products.models import Product
from apps.storage_location.models import StorageLocation

class RoboArmOperationsLog(Document):
    timestamp = DateTimeField(default=datetime.datetime.utcnow)

    operation_types_list = ["PICK", "PLACE", "MOVE", "IDLE", "STOP", "START"]
    operation_type = StringField(required=True, choices=operation_types_list)

    operation_status_list = ["SUCCESS", "FAILURE", "ABORT"]
    operation_status = StringField(default='SUCCESS', choices=operation_status_list, required=True)
    
    duration_ms = IntField(null=True)
    error_msg = StringField(null=True)
    
    product = ReferenceField(Product, null=True)
    location = ReferenceField(StorageLocation, null=True)

    meta = {'collection': 'tech_logs'}