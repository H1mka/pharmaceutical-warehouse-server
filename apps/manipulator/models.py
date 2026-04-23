from mongoengine import Document, StringField, DateTimeField, IntField, ReferenceField
from apps.storage_location.models import StorageLocation
from apps.products.models import Product
from datetime import datetime


class Manipulator(Document):
    status = StringField(default='OFF', required=True, choices=["OFF", "ON", "BUSY", "WAITING"])
    position = ReferenceField(StorageLocation, required=True, default="69e74dfdb5f2df9a6d4cfb10")
    
    meta = {'collection': 'manipulator/manipulators'}

class ManipulatorLog(Document):
    timestamp = DateTimeField(default=datetime.utcnow)
    max_attempts = 2

    operation_status_list = ["SUCCESS", "FAILURE", "ABORTED"]
    operation_status = StringField(default='SUCCESS', required=True, choices=operation_status_list)

    operation_types_list = ["PICK", "PUT", "MOVE", "STOP", "START"]
    operation_type = StringField(required=True, choices=operation_types_list)
    
    duration_ms = IntField(required=True)
    attempt = IntField(required=True)

    storage_location = ReferenceField(StorageLocation, null=True)
    product = ReferenceField(Product, null=True)
    product_quantity = IntField(null=True)

    error_msg = StringField(null=True)

    meta = {'collection': 'manipulator/logs',
            'indexes': [
                '-timestamp', 
            ]
    }