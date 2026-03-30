from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist, ValidationError
from .models import Inventory
from apps.products.models import Product
from apps.storage_location.models import StorageLocation
import json


def inventory_to_dict(inventory: Inventory) -> dict:
    """
    Serialize Inventory document to dict for JSON responses.
    """
    return {
        "id": str(inventory.id),
        "product_id": str(inventory.product.id) if inventory.product else None,
        "product_sku": inventory.product.sku if inventory.product else None,
        "storage_location_id": str(inventory.storage_location.id)
        if inventory.storage_location
        else None,
        "quantity": inventory.quantity,
        "reserved": inventory.reserved,
        "last_movement_at": inventory.last_movement_at.isoformat()
        if inventory.last_movement_at
        else None,
    }


@csrf_exempt
def inventory_list_create(request):
    return JsonResponse({"Message": "Inventory list create"}, status=200)


@csrf_exempt
def inventory_detail(request, inventory_id: str):
    return JsonResponse({"Message": f"Inventory detail with id: {inventory_id}"}, status=200)

from django.shortcuts import render

# Create your views here.