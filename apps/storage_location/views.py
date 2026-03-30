from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .models import StorageLocation
from mongoengine.errors import DoesNotExist, ValidationError
import json


def storage_location_to_dict(storage_location: StorageLocation) -> dict:
    """
    Utility to serialize StorageLocation to dict, suitable for JSON.
    """
    return {
        "id": str(storage_location.id),
        "zone": storage_location.zone,
        "shelf": storage_location.shelf,
        "row": storage_location.row,
        "column": storage_location.column,
        "capacity": storage_location.capacity,
        "current_load": storage_location.current_load,
        "is_active": storage_location.is_active,
        "created_at": storage_location.created_at.isoformat()
        if storage_location.created_at
        else None,
    }


@csrf_exempt
def storage_location_list_create(request):
    return JsonResponse({"Message": "Storage location create"}, status=200)


@csrf_exempt
def storage_location_detail(request, storage_location_id: str):
    return JsonResponse({"Message": f"Storage location detail with id: {storage_location_id}"}, status=200)