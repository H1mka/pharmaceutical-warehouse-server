import datetime

from mongoengine import DateTimeField, Document, ReferenceField, StringField

from apps.manipulator.models import ManipulatorLog
from apps.users.models import User


class OperationLogs(Document):
    operation_types_list = ["DISPENSE", "STORE", "MOVE", "FIX"]
    operation_type = StringField(required=True, choices=operation_types_list)

    user = ReferenceField(User, default=None, null=True)
    manipulator_task = ReferenceField(ManipulatorLog, default=None, null=True)

    message = StringField(default="")
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {"collection": "operation_logs"}
