from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .models import Product
from mongoengine.errors import DoesNotExist, ValidationError
import datetime
import json
import random
import numpy as np
import pandas as pd

from apps.inventory.models import Inventory
from apps.storage_location.models import StorageLocation
from apps.manipulator.models import Manipulator, ManipulatorLog
from apps.operation_logs.models import OperationLogs
from utils.pagination_helper import generate_pagination


def home(request):
    return HttpResponse("Home url")


def _normalize_zone_name(zone):
    return (zone or "").strip().upper().replace("-", "_").replace(" ", "_")

def _get_location_type(storage_location):
    location_type = getattr(storage_location, "location_type", None)
    if location_type and location_type != "STORAGE":
        return location_type

    normalized_zone = _normalize_zone_name(storage_location.zone)
    if normalized_zone in ["LOADING", "LOADING_ZONE"]:
        return "LOADING"
    if normalized_zone in ["DELIVERY", "DELIVERY_ZONE"]:
        return "DELIVERY"

    return "STORAGE"


def _is_storage_location(storage_location):
    return _get_location_type(storage_location) == "STORAGE"


def _get_special_storage_location(location_type):
    for storage_location in StorageLocation.objects(is_active=True):
        if _get_location_type(storage_location) == location_type:
            return storage_location

    raise ValidationError(f"{location_type.title()} storage location not found.")


def _send_logs(logs_to_create):
    import urllib.request
    import urllib.error
    url = "http://127.0.0.1:8000/control-panel/logs"
    created_logs = []
    for log_data in logs_to_create:
        req = urllib.request.Request(
            url, 
            data=json.dumps(log_data).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}, 
            method='POST'
        )
        try:
            with urllib.request.urlopen(req) as response:
                resp_body = response.read().decode('utf-8')
                resp_json = json.loads(resp_body)
                
                log_doc = ManipulatorLog.objects.get(id=resp_json["id"])
                created_logs.append(log_doc)

                if resp_json.get("operation_status") == "ABORTED":
                    return False, f"Manipulator hardware failure: {resp_json.get('error_msg')}", created_logs
        except urllib.error.URLError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            try:
                err_dict = json.loads(error_body)
                return False, err_dict.get("error", str(e)), created_logs
            except Exception:
                return False, error_body or str(e), created_logs
    return True, "", created_logs

# For emergency return of product to the place where it was taken from when two operations fail in a row
def _handle_emergency_return(created_manipulator_logs, product):
    if not created_manipulator_logs:
        return

    held_qty = 0
    last_pick_loc = None

    for log in created_manipulator_logs:
        if log.operation_status == "SUCCESS":
            if log.operation_type == "PICK":
                held_qty += (log.product_quantity or 0)
                last_pick_loc = log.storage_location
            elif log.operation_type == "PUT":
                held_qty -= (log.product_quantity or 0)
    
    if held_qty > 0 and last_pick_loc:
        move_log = ManipulatorLog(
            operation_type="MOVE",
            operation_status="SUCCESS",
            duration_ms=2000,
            attempt=1,
            storage_location=last_pick_loc,
            product=product,
            product_quantity=held_qty,
            error_msg="Emergency return MOVE"
        )
        move_log.save()
        
        put_log = ManipulatorLog(
            operation_type="PUT",
            operation_status="SUCCESS",
            duration_ms=2000,
            attempt=1,
            storage_location=last_pick_loc,
            product=product,
            product_quantity=held_qty,
            error_msg="Emergency return PUT"
        )
        put_log.save()

        manipulator = Manipulator.objects.first()
        if manipulator:
            manipulator.update(position=last_pick_loc)



def allocate_product_quantity(alloc_product: Product, quantity: int):
    # total_quantity = quantity
    date = datetime.datetime.utcnow()
    loading_zone = _get_special_storage_location("LOADING")
    remaining_quantity = quantity
    logs_to_create = []
    history = []

    logs_to_create.append(
        {
            "operation_type": "PICK",
            "storage_location": str(loading_zone.id),
            "product": str(alloc_product.id),
            "product_quantity": remaining_quantity
        }
    )

    storage_locations = [
        location
        for location in StorageLocation.objects(is_active=True).order_by("zone", "row", "column", "id")
        if _is_storage_location(location)
    ]
    
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
                
                # total_quantity -= add_qty

                logs_to_create.append(
                    {
                        "operation_type": "MOVE",
                        "storage_location": str(loc.id),
                        "product": str(alloc_product.id),
                        "product_quantity": remaining_quantity
                    }
                )
                logs_to_create.append(
                    {
                        "operation_type": "PUT",
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
                created_at=date
            )
            inventory.save()

            history.append((inventory, 0, True))

            # total_quantity -= add_qty

            logs_to_create.append(
                {
                    "operation_type": "MOVE",
                    "storage_location": str(loc.id),
                    "product": str(alloc_product.id),
                    "product_quantity": remaining_quantity
                }
            )
            logs_to_create.append(
                {
                    "operation_type": "PUT",
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
        success, err_msg, _ = _send_logs(logs_to_create)

    if not success:
        success_put_count = sum(
            1 for log in created_manipulator_logs 
            if log.operation_type == "PUT" and log.operation_status == "SUCCESS"
        )
        history_to_revert = history[success_put_count:]
        
        for item, old_qty, is_new in reversed(history_to_revert):
            if is_new:
                item.delete()
            else:
                item.quantity = old_qty
                item.save()
        
        _handle_emergency_return(created_manipulator_logs, alloc_product)

        return False, err_msg

    return True, ""


def dispense_product_quantity(alloc_product: Product, quantity: int):
    delivery_zone = _get_special_storage_location("DELIVERY")

    remaining_quantity = quantity
    history = []
    logs_to_create = []
    created_manipulator_logs = []
    created_operation_log = None

    inventories = Inventory.objects(product=alloc_product, quantity__gt=0).order_by("created_at", "quantity")

    for inventory in inventories:
        if remaining_quantity <= 0:
            break
            
        loc = inventory.storage_location
        if not loc.is_active or not _is_storage_location(loc):
            continue
            
        current_qty = inventory.quantity or 0
        take_qty = min(remaining_quantity, current_qty)

        if take_qty > 0:
            history.append((inventory, inventory.quantity, False))

            inventory.quantity -= take_qty
            inventory.save()

            logs_to_create.append(
                {
                    "operation_type": "PICK",
                    "storage_location": str(loc.id),
                    "product": str(alloc_product.id),
                    "product_quantity": take_qty
                }
            )
            logs_to_create.append(
                {
                    "operation_type": "MOVE",
                    "storage_location": str(delivery_zone.id),
                    "product": str(alloc_product.id),
                    "product_quantity": take_qty
                }
            )
            logs_to_create.append(
                {
                    "operation_type": "PUT",
                    "storage_location": str(delivery_zone.id),
                    "product": str(alloc_product.id),
                    "product_quantity": take_qty
                }
            )

            remaining_quantity -= take_qty

    dispensed_quantity = quantity - remaining_quantity

    if remaining_quantity > 0:
        err_msg = f"Not enough product quantity in storage. Missing quantity: {remaining_quantity}"
        success = False
    else:
        try:
            success, err_msg, created_manipulator_logs = _send_logs(logs_to_create)
            if success:
                created_operation_log = OperationLogs(
                    operation_type="DISPENSE",
                    product=alloc_product,
                    product_quantity=dispensed_quantity,
                    manipulator_task=created_manipulator_logs[-1] if created_manipulator_logs else None,
                    message=f"Dispensed {dispensed_quantity} units of product {alloc_product.sku}",
                )
                created_operation_log.save()
        except Exception as e:
            success, err_msg = False, str(e)

    if not success:
        success_put_count = sum(
            1 for log in created_manipulator_logs 
            if log.operation_type == "PUT" and log.operation_status == "SUCCESS"
        )
        history_to_revert = history[success_put_count:]

        for item, old_qty, is_new in reversed(history_to_revert):
            if is_new:
                item.delete()
            else:
                item.quantity = old_qty
                item.save()

        if created_operation_log:
            created_operation_log.delete()

        _handle_emergency_return(created_manipulator_logs, alloc_product)

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

# Analitics: analyze product/medicine popularity

def _parse_analytics_datetime(value, field_name):
    if not value:
        return None

    try:
        parsed_value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(
            f"Invalid '{field_name}' format. Use ISO format, for example 2026-05-02 or 2026-05-02T10:00:00"
        )

    if parsed_value.tzinfo:
        parsed_value = parsed_value.astimezone(datetime.timezone.utc).replace(tzinfo=None)

    return parsed_value


def _operation_logs_to_popularity_dataframe(logs):
    rows = []

    for log in logs:
        product = log.product
        if not product:
            continue

        rows.append(
            {
                "product_id": str(product.id),
                "sku": product.sku,
                "name": product.name,
                "manufacturer": product.manufacturer,
                "quantity": log.product_quantity or 0,
                "created_at": log.created_at or datetime.datetime.utcnow(),
            }
        )

    return pd.DataFrame(rows)


def _empty_product_popularity_response(start_date, end_date, limit, sort_by):
    return {
        "success": True,
        "filters": {
            "from": start_date.isoformat() if start_date else None,
            "to": end_date.isoformat() if end_date else None,
            "limit": limit,
            "sort_by": sort_by,
        },
        "summary": {
            "products_count": 0,
            "dispense_count": 0,
            "total_dispensed_quantity": 0,
            "average_dispensed_quantity": 0,
            "top_product": None,
        },
        "chart": {
            "labels": [],
            "datasets": [
                {
                    "label": "Dispensed quantity",
                    "data": [],
                }
            ],
        },
        "items": [],
    }


@csrf_exempt
def product_popularity_analytics(request):
    """
    GET /analytics/products/popularity

    Query params:
      from=ISO datetime/date
      to=ISO datetime/date
      limit=positive integer, default 10
      sort_by=quantity|count
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    sort_by = request.GET.get("sort_by", "quantity")
    if sort_by not in ["quantity", "count"]:
        return JsonResponse(
            {"success": False, "error": "Invalid sort_by. Use one of: quantity, count"},
            status=400,
        )

    try:
        limit = int(request.GET.get("limit", 10))
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid limit. Use a positive integer"}, status=400)

    if limit <= 0:
        return JsonResponse({"success": False, "error": "Invalid limit. Use a positive integer"}, status=400)

    try:
        start_date = _parse_analytics_datetime(request.GET.get("from"), "from")
        end_date = _parse_analytics_datetime(request.GET.get("to"), "to")
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

    if start_date and end_date and start_date > end_date:
        return JsonResponse({"success": False, "error": "'from' cannot be later than 'to'"}, status=400)

    query_filter = {"operation_type": "DISPENSE", "product__ne": None}
    if start_date:
        query_filter["created_at__gte"] = start_date
    if end_date:
        query_filter["created_at__lte"] = end_date

    logs = list(OperationLogs.objects(**query_filter).order_by("created_at"))
    if not logs:
        return JsonResponse(_empty_product_popularity_response(start_date, end_date, limit, sort_by), status=200)

    df = _operation_logs_to_popularity_dataframe(logs)
    if df.empty:
        return JsonResponse(_empty_product_popularity_response(start_date, end_date, limit, sort_by), status=200)

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)

    popularity = (
        df.groupby(["product_id", "sku", "name", "manufacturer"], dropna=False)
        .agg(
            dispensed_quantity=("quantity", "sum"),
            dispense_count=("quantity", "size"),
            last_dispensed_at=("created_at", "max"),
        )
        .reset_index()
    )

    total_dispensed_quantity = int(np.sum(popularity["dispensed_quantity"].to_numpy()))
    total_dispense_count = int(np.sum(popularity["dispense_count"].to_numpy()))
    products_count = int(popularity["product_id"].nunique())
    sort_column = "dispensed_quantity" if sort_by == "quantity" else "dispense_count"

    popularity = popularity.sort_values(
        by=[sort_column, "dispensed_quantity", "dispense_count", "name"],
        ascending=[False, False, False, True],
    ).head(limit)

    items = []
    for rank, (_, row) in enumerate(popularity.iterrows(), start=1):
        dispensed_quantity = int(row["dispensed_quantity"])
        dispense_count = int(row["dispense_count"])
        items.append(
            {
                "rank": rank,
                "product_id": row["product_id"],
                "sku": row["sku"],
                "name": row["name"],
                "manufacturer": row["manufacturer"] if pd.notna(row["manufacturer"]) else None,
                "dispensed_quantity": dispensed_quantity,
                "dispense_count": dispense_count,
                "quantity_share_percent": float(
                    np.round((dispensed_quantity / total_dispensed_quantity) * 100, 2)
                )
                if total_dispensed_quantity
                else 0,
                "count_share_percent": float(np.round((dispense_count / total_dispense_count) * 100, 2))
                if total_dispense_count
                else 0,
                "last_dispensed_at": row["last_dispensed_at"].isoformat()
                if pd.notna(row["last_dispensed_at"])
                else None,
            }
        )

    top_product = items[0] if items else None

    return JsonResponse(
        {
            "success": True,
            "filters": {
                "from": start_date.isoformat() if start_date else None,
                "to": end_date.isoformat() if end_date else None,
                "limit": limit,
                "sort_by": sort_by,
            },
            "summary": {
                "products_count": products_count,
                "dispense_count": total_dispense_count,
                "total_dispensed_quantity": total_dispensed_quantity,
                "average_dispensed_quantity": float(
                    np.round(total_dispensed_quantity / total_dispense_count, 2)
                )
                if total_dispense_count
                else 0,
                "top_product": top_product,
            },
            "chart": {
                "labels": [item["name"] for item in items],
                "datasets": [
                    {
                        "label": "Dispensed quantity",
                        "data": [item["dispensed_quantity"] for item in items],
                    },
                    {
                        "label": "Dispense operations",
                        "data": [item["dispense_count"] for item in items],
                    },
                ],
            },
            "items": items,
        },
        status=200,
    )


@csrf_exempt
def products_list_create(request):
    """
    GET  /products      -> list all products
    POST /products      -> create a product
    """
    if request.method == "GET":
        product_name = request.GET.get("name", "")
        products_qs = Product.objects.all()

        if product_name:
            products_qs = products_qs.filter(name__icontains=product_name)

        try:
            pagination_data, skip = generate_pagination(request, products_qs.count())
        except ValueError as e:
            return JsonResponse({
                    "success": False,
                    "data": [],
                    "error": str(e),
                }, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "error": "Unknown error"}, status=500)

        products = list(
            products_qs.order_by("-created_at", "-id")
            .skip(skip)
            .limit(pagination_data['page_size'])
        )

        product_quantity_by_id = {str(product.id): 0 for product in products}

        if products:
            inventories = Inventory.objects(product__in=products).only("product", "quantity", "storage_location")

            for inventory in inventories:
                if not _is_storage_location(inventory.storage_location):
                    continue

                product_id = str(inventory.product.id)
                product_quantity_by_id[product_id] = product_quantity_by_id.get(product_id, 0) + (inventory.quantity or 0)

        data = []
        for product in products:
            product_data = product_to_dict(product)
            product_data["quantity"] = product_quantity_by_id.get(str(product.id), 0)
            data.append(product_data)
        
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
        
        product.sku = body.get("sku")
        product.name = body.get("name")
        
        product.manufacturer = body.get("manufacturer")
        product.form = body.get("form")
        product.dosage = body.get("dosage")
        product.package_size = body.get("package_size")
        quantity = body.get('quantity')

        expiration_date = body.get("expiration_date")
        if expiration_date:
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
    POST   /products/<sku>/receive -> receive_product
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


@csrf_exempt
def dispense_product(request, sku: str):
    """
    POST   /products/<sku>/dispense -> dispense_product
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
        dispense_success, remaining_qty = dispense_product_quantity(product, quantity)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if not dispense_success:
        return JsonResponse({"error": remaining_qty}, status=400)

    product.updated_at = datetime.datetime.utcnow()
    product.save()

    return JsonResponse(
        {
            "success": True,
            "message": "Product dispensed",
            "sku": product.sku,
            "dispensed_quantity": quantity,
        },
        status=200,
    )
