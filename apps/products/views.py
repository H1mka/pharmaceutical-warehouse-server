from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .models import Product
from mongoengine.errors import DoesNotExist, ValidationError
import datetime
import json

# models
from apps.inventory.models import Inventory
from apps.storage_location.models import StorageLocation


def home(request):
    return HttpResponse("Home url")


def product_to_dict(product: Product) -> dict:
    """
    Utility to serialize Product to dict, suitable for JSON.
    """
    return {
        "id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "manufacturer": product.manufacturer,
        "form": product.form,
        "dosage": product.dosage,
        "package_size": product.package_size,
        "expiration_date": product.expiration_date.isoformat()
        if product.expiration_date
        else None,
        "created_at": product.created_at.isoformat()
        if product.created_at
        else None,
        
        "updated_at": product.updated_at.isoformat()
        
        if product.updated_at
        else None,
    }


@csrf_exempt
def products_list_create(request):
    return JsonResponse({"Message": "Products list create"}, status=200)


@csrf_exempt
def product_detail(request, sku: str):
    return JsonResponse({"Message": f"Product detail with sku: {sku}"}, status=200)
