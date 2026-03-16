import datetime

from mongoengine import DateTimeField, Document, StringField


class User(Document):
    username = StringField(required=True, unique=True)
    first_name = StringField(required=True)
    last_name = StringField(required=True)
    password = StringField(required=True)

    role = StringField(
        choices=["admin", "pharmacist"],
        default="pharmacist"
    )

    created_at = DateTimeField(default=datetime.datetime.utcnow)