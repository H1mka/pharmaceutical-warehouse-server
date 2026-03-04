from django.db import models
from mongoengine import Document, StringField, IntField, DateTimeField
import datetime

class Product(Document):
    sku = StringField(required=True, unique=True) # unique articule
    name = StringField(required=True)
    manufacturer = StringField()
    form = StringField()
    dosage = StringField()
    package_size = IntField()
    expiration_date = DateTimeField()
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'products'}
