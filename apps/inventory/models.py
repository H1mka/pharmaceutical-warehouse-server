from django.db import models
from mongoengine import Document, StringField, IntField, DateTimeField, ReferenceField
import datetime
from apps.products.models import Product
from apps.storage_location.models import StorageLocation

# Create your models here.

class Inventory(Document):
  product = ReferenceField(Product, required=True)
  storage_location = ReferenceField(StorageLocation, required=True, unique=True)

  quantity = IntField(required=True)
  reserved = IntField(default=0)
  created_at = DateTimeField(default=datetime.datetime.utcnow)