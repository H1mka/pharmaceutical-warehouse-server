import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
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
        "id": str(log.id),
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "operation_type": log.operation_type,
        "product_id": str(log.product.id) if log.product else None,
        "status": log.operation_status,
        "duration_ms": log.duration_ms,
        "error_msg": log.error_msg,
        "location_id": str(log.location.id) if log.location else None,
    }


@csrf_exempt
def logs_list_create(request):
    return JsonResponse({"Message": "Log list create"}, status=200)


@csrf_exempt
def log_detail(request, log_id: str):
    return JsonResponse({"Message": f"Log detail with id: {log_id}"}, status=200)
