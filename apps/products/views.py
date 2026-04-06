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
    """
    GET  /products      -> list all products
    POST /products      -> create a product
    """
    if request.method == "GET":
        products = Product.objects.all()
        data = [product_to_dict(p) for p in products]
        return JsonResponse(data, safe=False, status=200)

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        print('POST METHOD', body)

        product = Product()
        # required fields
        product.sku = body.get("sku")
        product.name = body.get("name")
        # optional fields
        product.manufacturer = body.get("manufacturer")
        product.form = body.get("form")
        product.dosage = body.get("dosage")
        product.package_size = body.get("package_size")
        quantity = body.get('quantity')

        expiration_date = body.get("expiration_date")
        if expiration_date:
            # wait for ISO string, for example "2025-12-31T00:00:00"
            try:
                product.expiration_date = datetime.datetime.fromisoformat(
                    expiration_date
                )
            except ValueError:
                return JsonResponse(
                    {
                        "error": "Field 'expiration_date' must be in ISO format, for example '2025-12-31T00:00:00'"
                    },
                    status=400,
                )

        try:
            duplicate_product = Product.objects(sku=body.get("sku")).first() or {}
            if duplicate_product:
                return JsonResponse({"error": "Tried to save duplicate unique sku values"}, status=400)
        except ValidationError as e:
            return JsonResponse({"error": "Tried to save duplicate unique sku values"}, status=400)

        try:
            product.save()
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)
        
        # If quantity is specified, distribute it across free active storage locations.
        # One storage location can contain only one inventory record.
        if isinstance(quantity, int) and quantity > 0:
            free_locations = []
            for loc in StorageLocation.objects(is_active=True).order_by(
                "zone", "shelf", "row", "column", "id"
            ):
                if not Inventory.objects(storage_location=loc).first():
                    free_locations.append(loc)

            remaining_quantity = quantity
            created_inventories = []

            for loc in free_locations:
                if remaining_quantity <= 0:
                    break

                loc_capacity = loc.capacity or 0
                if loc_capacity <= 0:
                    continue

                quantity_for_location = min(remaining_quantity, loc_capacity)
                inventory = Inventory(
                    product=product,
                    storage_location=loc,
                    quantity=quantity_for_location,
                    reserved=0,
                )

                try:
                    inventory.save()
                except ValidationError as e:
                    for created_inventory in created_inventories:
                        created_inventory.delete()
                    product.delete()
                    return JsonResponse({"error": str(e)}, status=400)

                created_inventories.append(inventory)
                remaining_quantity -= quantity_for_location

            if remaining_quantity > 0:
                for created_inventory in created_inventories:
                    created_inventory.delete()
                product.delete()
                return JsonResponse(
                    {
                        "error": (
                            "Not enough free storage capacity to place all product quantity. "
                            f"Unplaced quantity: {remaining_quantity}"
                        )
                    },
                    status=400,
                )


        return JsonResponse(product_to_dict(product), status=200)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def product_detail(request, sku: str):
    """
    GET    /products/<sku>/ -> get one product
    PUT    /products/<sku>/ -> full update
    PATCH  /products/<sku>/ -> partial update
    DELETE /products/<sku>/ -> delete a product
    """
    try:
        product = Product.objects.get(sku=sku)
    except DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(product_to_dict(product), status=200)

    if request.method in ["PUT", "PATCH"]:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # For PUT we usually expect a full body, for PATCH we expect a partial body.
        # Here we support both variants, updating only the received fields.
        updatable_fields = [
            "name",
            "manufacturer",
            "form",
            "dosage",
            "package_size",
            "expiration_date",
        ]

        for field in updatable_fields:
            if field in body:
                if field == "expiration_date" and body[field] is not None:
                    try:
                        setattr(
                            product,
                            field,
                            datetime.datetime.fromisoformat(body[field]),
                        )
                    except ValueError:
                        return JsonResponse(
                            {
                                "error": "Field 'expiration_date' must be in ISO format, for example '2025-12-31T00:00:00'"
                            },
                            status=400,
                        )
                else:
                    setattr(product, field, body[field])

        product.updated_at = datetime.datetime.utcnow()

        try:
            product.save()
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(product_to_dict(product), status=200)

    if request.method == "DELETE":
        product.delete()
        return JsonResponse({"message": "Product deleted"}, status=200)

    return HttpResponseNotAllowed(["GET", "PUT", "PATCH", "DELETE"])
