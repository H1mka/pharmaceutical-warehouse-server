from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .models import Product
from mongoengine.errors import DoesNotExist, ValidationError
import datetime
import json

# models
from apps.inventory.models import Inventory
from apps.storage_location.models import StorageLocation
from apps.manipulator.models import ManipulatorLog
from utils.pagination_helper import generate_pagination


def home(request):
    return HttpResponse("Home url")


def _send_logs(logs_to_create):
    import urllib.request
    import urllib.error
    url = "http://127.0.0.1:8000/control-panel/logs"
    for log_data in logs_to_create:
        req = urllib.request.Request(
            url, 
            data=json.dumps(log_data).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}, 
            method='POST'
        )
        try:
            with urllib.request.urlopen(req) as response:
                pass
        except urllib.error.URLError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            try:
                err_dict = json.loads(error_body)
                return False, err_dict.get("error", str(e))
            except Exception:
                return False, error_body or str(e)
    return True, ""


def allocate_product_quantity(alloc_product: Product, quantity: int):
    total_quantity = quantity
    remaining_quantity = quantity
    history = []
    logs_to_create = []

    logs_to_create.append(
        {
            "operation_status": "SUCCESS",
            "operation_type": "PICK",
            "duration_ms": 1500,
            "attempt": 1,
            "storage_location": "69e74dfdb5f2df9a6d4cfb10",
            "product": str(alloc_product.id),
            "product_quantity": remaining_quantity
        }
    )

    storage_locations = StorageLocation.objects(is_active=True).order_by("zone", "row", "column", "id")
    
    # Step 1: add product to existing inventory
    for loc in storage_locations:
        if remaining_quantity <= 0:
            break
        
        inventory = Inventory.objects(storage_location=loc, product=alloc_product).first()

        if inventory:
            capacity = loc.capacity or 0
            current_qty = inventory.quantity or 0
            can_add = capacity - current_qty

            if can_add > 0:
                add_qty = min(remaining_quantity, can_add)

                history.append((inventory, inventory.quantity, False))

                inventory.quantity += add_qty
                inventory.save()
                
                total_quantity -= add_qty

                logs_to_create.append(
                    {
                        "operation_status": "SUCCESS",
                        "operation_type": "MOVE",
                        "duration_ms": 1500,
                        "attempt": 1,
                        "storage_location": str(loc.id),
                        "product": str(alloc_product.id),
                        "product_quantity": remaining_quantity
                    }
                )
                logs_to_create.append(
                    {
                        "operation_status": "SUCCESS",
                        "operation_type": "PUT",
                        "duration_ms": 1500,
                        "attempt": 1,
                        "storage_location": str(loc.id),
                        "product": str(alloc_product.id),
                        "product_quantity": add_qty
                    }
                )

                remaining_quantity -= add_qty

    # Step 2: create new inventories with empty locations
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

            history.append((inventory, 0, True))

            total_quantity -= add_qty

            logs_to_create.append(
                {
                    "operation_status": "SUCCESS",
                    "operation_type": "MOVE",
                    "duration_ms": 1500,
                    "attempt": 1,
                    "storage_location": str(loc.id),
                    "product": str(alloc_product.id),
                    "product_quantity": remaining_quantity
                }
            )
            logs_to_create.append(
                {
                    "operation_status": "SUCCESS",
                    "operation_type": "PUT",
                    "duration_ms": 1500,
                    "attempt": 1,
                    "storage_location": str(loc.id),
                    "product": str(alloc_product.id),
                    "product_quantity": add_qty
                }
            )

            remaining_quantity -= add_qty

    if remaining_quantity > 0:
        err_msg = f"Not enough free storage capacity to place all product quantity. Unplaced quantity: {remaining_quantity}"
        success = False
    else:
        success, err_msg = _send_logs(logs_to_create)

    if not success:
        for item, old_qty, is_new in reversed(history):
            if is_new:
                item.delete()
            else:
                item.quantity = old_qty
                item.save()
        

        return False, err_msg

    return True, ""


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
        try:
            pagination_data, skip = generate_pagination(request, Product.objects.count())
        except ValueError as e:
            return JsonResponse({
                    "success": False,
                    "data": [],
                    "error": str(e),
                }, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "error": "Unknown error"}, status=500)

        products = (
            Product.objects.order_by("-created_at", "-id").skip(skip).limit(pagination_data['page_size'])
        )
        data = [product_to_dict(p) for p in products]
        
        return JsonResponse(
            {
                "success": True,
                "data": data,
                "extra": pagination_data,
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
                return JsonResponse({"error": remaining_quantity}, status=400)


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
    """
    POST   /products/<sku>/receive?quantity=<quantity> -> receive_product
    """
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

    try:
        alloc_success, remaining_qty = allocate_product_quantity(product, quantity)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if not alloc_success:
        return JsonResponse({"error": remaining_qty}, status=400)

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
