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
    """
    GET  /inventory          -> list all inventory records
    POST /inventory          -> create inventory record
    """
    if request.method == "GET":
        items = Inventory.objects.all()
        data = [inventory_to_dict(i) for i in items]
        return JsonResponse(data, safe=False, status=200)

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        product_id = body.get("product_id")
        product_sku = body.get("product_sku")
        storage_location_id = body.get("storage_location_id")
        quantity = body.get("quantity")
        reserved = body.get("reserved", 0)

        if quantity is None:
            return JsonResponse({"error": "Field 'quantity' is required"}, status=400)

        # Resolve product
        try:
            if product_id:
                product = Product.objects.get(id=product_id)
            elif product_sku:
                product = Product.objects.get(sku=product_sku)
            else:
                return JsonResponse(
                    {"error": "Either 'product_id' or 'product_sku' is required"},
                    status=400,
                )
        except DoesNotExist:
            return JsonResponse({"error": "Product not found"}, status=404)

        # Resolve storage location
        if not storage_location_id:
            return JsonResponse(
                {"error": "Field 'storage_location_id' is required"}, status=400
            )

        try:
            storage_location = StorageLocation.objects.get(id=storage_location_id)
        except DoesNotExist:
            return JsonResponse({"error": "StorageLocation not found"}, status=404)

        item = Inventory(
            product=product,
            storage_location=storage_location,
            quantity=quantity,
            reserved=reserved,
        )

        try:
            item.save()
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(inventory_to_dict(item), status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def inventory_detail(request, inventory_id: str):
    """
    GET    /inventory/<id>   -> get one inventory record
    PUT    /inventory/<id>   -> full update
    PATCH  /inventory/<id>   -> partial update
    DELETE /inventory/<id>   -> delete inventory record
    """
    try:
        item = Inventory.objects.get(id=inventory_id)
    except DoesNotExist:
        return JsonResponse({"error": "Inventory not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(inventory_to_dict(item), status=200)

    if request.method in ["PUT", "PATCH"]:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        updatable_fields = ["quantity", "reserved"]

        for field in updatable_fields:
            if field in body:
                setattr(item, field, body[field])

        try:
            item.save()
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(inventory_to_dict(item), status=200)

    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"message": "Inventory deleted"}, status=200)

    return HttpResponseNotAllowed(["GET", "PUT", "PATCH", "DELETE"])

from django.shortcuts import render

# Create your views here.