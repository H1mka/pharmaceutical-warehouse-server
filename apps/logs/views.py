import json
import datetime
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist, ValidationError

from apps.logs.models import RoboArmOperationsLog
from apps.products.models import Product
from apps.storage_location.models import StorageLocation


def log_to_dict(log: RoboArmOperationsLog) -> dict:
    """
    Utility to serialize RoboArmOperationsLog to dict for JSON response.
    """
    return {
        "id": str(log.id), # !!!
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "operation_type": log.operation_type,
        "product_id": str(log.product.id) if log.product else None,
        "status": log.status,
        "duration_ms": log.duration_ms,
        "error_msg": log.error_msg,
        "location_id": str(log.location.id) if log.location else None,
    }


@csrf_exempt
def logs_list_create(request):
    """
    GET  /logs/ -> list all logs (with pagination support)
    POST /logs/ -> create a new log entry
    """
    if request.method == "GET":
        # Get limit and skip for pagination (default to last 50 logs)
        try:
            limit = int(request.GET.get('limit', 50))
            skip = int(request.GET.get('skip', 0))
        except ValueError:
            limit = 50
            skip = 0

        # Sort by timestamp descending to get the newest logs first
        logs = RoboArmOperationsLog.objects.order_by('-timestamp').skip(skip).limit(limit)
        data = [log_to_dict(log) for log in logs]
        return JsonResponse(data, safe=False, status=200)

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        log_entry = RoboArmOperationsLog()
        

        # Required field
        log_entry.operation_type = body.get("operation_type")
        
        # Optional fields
        if "status" in body:
            log_entry.status = body.get("status")
        if "duration_ms" in body:
            log_entry.duration_ms = body.get("duration_ms")
        if "error_msg" in body:
            log_entry.error_msg = body.get("error_msg")
        
        # Handling relations (ReferenceField in MongoEngine)
        product_id = body.get("product_id")
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
                log_entry.product = product
            except DoesNotExist:
                return JsonResponse({"error": f"Product with id {product_id} not found"}, status=400)
            except ValidationError:
                return JsonResponse({"error": "Invalid Product ID format"}, status=400)

        location_id = body.get("location_id")
        if location_id:
            try:
                location = StorageLocation.objects.get(id=location_id)
                log_entry.location = location
            except DoesNotExist:
                return JsonResponse({"error": f"StorageLocation with id {location_id} not found"}, status=400)
            except ValidationError:
                return JsonResponse({"error": "Invalid StorageLocation ID format"}, status=400)

        # Save to MongoDB
        try:
            log_entry.save()
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(log_to_dict(log_entry), status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def log_detail(request, log_id: str):
    """
    GET    /logs/<id>/ -> get one log entry details
    DELETE /logs/<id>/ -> delete a log entry
    """
    try:
        log_entry = RoboArmOperationsLog.objects.get(id=log_id)
    except DoesNotExist:
        return JsonResponse({"error": "Log entry not found"}, status=404)
    except ValidationError:
         return JsonResponse({"error": "Invalid Log ID format"}, status=400)

    if request.method == "GET":
        return JsonResponse(log_to_dict(log_entry), status=200)

    if request.method == "DELETE":
        log_entry.delete()
        return JsonResponse({"message": "Log entry deleted"}, status=200)

    return HttpResponseNotAllowed(["GET", "DELETE"])
