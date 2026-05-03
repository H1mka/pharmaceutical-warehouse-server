import datetime

from mongoengine import DateTimeField, Document, IntField, ReferenceField, StringField

from apps.manipulator.models import ManipulatorLog
from apps.products.models import Product
from apps.users.models import User


class OperationLogs(Document):
    operation_types_list = ["DISPENSE", "STORE", "MOVE", "FIX"]
    operation_type = StringField(required=True, choices=operation_types_list)

    user = ReferenceField(User, default=None, null=True)
    product = ReferenceField(Product, default=None, null=True)
    manipulator_task = ReferenceField(ManipulatorLog, default=None, null=True)

    product_quantity = IntField(default=0)
    message = StringField(default="")
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {"collection": "operation_logs"}
