from django.db import models
from mongoengine import Document, StringField, IntField, DateTimeField, BooleanField
import datetime

class StorageLocation(Document):
    zone = StringField(required=True)
    row = IntField(required=True)
    column = IntField(required=True)
    capacity = IntField(required=True)
    is_active = BooleanField(required=True, default=True)
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'storage_locations'}