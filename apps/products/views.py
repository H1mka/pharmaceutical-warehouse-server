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

def allocate_product_quantity(alloc_product: Product, quantity: int):
    remaining_quantity = quantity
    history = []

    storage_locations = StorageLocation.objects(is_active=True).order_by("zone", "row", "column", "id")

    # Step 1: add product to existing inventory
    for loc in storage_locations:
        if remaining_quantity <= 0:
            break
        
        inventory = Inventory.objects(storage_location=loc, product=alloc_product).first()
        print(loc.id, inventory)

        if inventory:
            capacity = loc.capacity or 0
            current_qty = inventory.quantity or 0
            can_add = capacity - current_qty

            if can_add > 0:
                add_qty = min(remaining_quantity, can_add)

                # Save state before changes
                history.append((inventory, inventory.quantity, False))

                inventory.quantity += add_qty
                inventory.save()
                remaining_quantity -= add_qty


    # Step 2: create new inventories with empty locations
    if remaining_quantity <= 0:
        return True, 0

    # empty storage locations
    free_locations = []

    # find empty storage locations
    for loc in storage_locations:
        if remaining_quantity <= 0:
            break

        if not Inventory.objects(storage_location=loc).first():
            max_capacity = loc.capacity or 0
            if max_capacity <= 0:
                continue

            add_qty = min(remaining_quantity, max_capacity)
            inventory = Inventory(
                product=alloc_product,
                storage_location=loc,
                quantity=add_qty,
                reserved=0,
            )
            inventory.save()

            # save history for backup
            history.append((inventory, 0, True))
            remaining_quantity -= add_qty

    if remaining_quantity > 0:
        for item, old_qty, is_new in reversed(history):
            if is_new:
                item.delete()
            else:
                item.quantity = old_qty
                item.save()

        return False, remaining_quantity

    return True, 0


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
        page_raw = request.GET.get("page", "1")
        page_size_raw = request.GET.get("page_size", "10")

        try:
            page = int(page_raw)
            page_size = int(page_size_raw)
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "success": False,
                    "data": [],
                    "extra": {"error": "Query params 'page' and 'page_size' must be integers"},
                },
                status=400,
            )

        if page <= 0 or page_size <= 0:
            return JsonResponse(
                {
                    "success": False,
                    "data": [],
                    "extra": {
                        "error": "Query params 'page' and 'page_size' must be positive integers"
                    },
                },
                status=400,
            )

        page_size = min(page_size, 100)
        total_items = Product.objects.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)

        if page > total_pages and total_items > 0:
            return JsonResponse(
                {
                    "success": False,
                    "data": [],
                    "extra": {
                        "error": "Page is out of range",
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_items,
                        "total_pages": total_pages,
                    },
                },
                status=400,
            )

        skip = (page - 1) * page_size
        products = (
            Product.objects.order_by("-created_at", "-id").skip(skip).limit(page_size)
        )
        data = [product_to_dict(p) for p in products]

        return JsonResponse(
            {
                "success": True,
                "data": data,
                "extra": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages
                },
            },
            status=200,
        )

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
        
        if quantity is not None:
            if not isinstance(quantity, int) or quantity <= 0:
                product.delete()
                return JsonResponse(
                    {"error": "Field 'quantity' must be a positive integer"},
                    status=400,
                )

            try:
                alloc_success, remaining_quantity = allocate_product_quantity(product, quantity)
            except ValidationError as e:
                product.delete()
                return JsonResponse({"error": str(e)}, status=400)

            if not alloc_success:
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


@csrf_exempt
def receive_product(request, sku: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        product = Product.objects.get(sku=sku)
    except DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=404)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    quantity = body.get("quantity")
    if not isinstance(quantity, int) or quantity <= 0:
        return JsonResponse(
            {"error": "Field 'quantity' must be a positive integer"},
            status=400,
        )

    # alloc_success, remaining_quantity = allocate_product_quantity(product, quantity)
    # return JsonResponse({"error": ""}, status=400)

    try:
        alloc_success, remaining_qty = allocate_product_quantity(product, quantity)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if not alloc_success:
        return JsonResponse(
            {
                "error": (
                    "Not enough free storage capacity to place all product quantity. "
                    f"Unplaced quantity: {remaining_qty}"
                )
            },
            status=400,
        )

    product.updated_at = datetime.datetime.utcnow()
    product.save()

    return JsonResponse(
        {
            "success": True,
            "message": "Product received and placed in storage",
            "sku": product.sku,
            "added_quantity": quantity,
        },
        status=200,
    )
