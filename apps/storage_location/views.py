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
        "is_active": storage_location.is_active,
        "created_at": storage_location.created_at.isoformat()
        if storage_location.created_at
        else None,
    }


@csrf_exempt
def storage_location_list_create(request):
    """
    GET  /storage-locations        -> list all storage locations
    POST /storage-locations        -> create storage location
    """
    if request.method == "GET":
        storage_locations = StorageLocation.objects.all()
        data = [storage_location_to_dict(s) for s in storage_locations]
        return JsonResponse(data, safe=False, status=200)

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        storage_location = StorageLocation()
        storage_location.zone = body.get("zone")
        storage_location.shelf = body.get("shelf")
        storage_location.row = body.get("row")
        storage_location.column = body.get("column")
        storage_location.capacity = body.get("capacity")
        storage_location.is_active = body.get("is_active", True)

        try:
            storage_location.save()
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(storage_location_to_dict(storage_location), status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def storage_location_detail(request, storage_location_id: str):
    """
    GET    /storage-locations/<id> -> get one storage location
    PUT    /storage-locations/<id> -> full update
    PATCH  /storage-locations/<id> -> partial update
    DELETE /storage-locations/<id> -> delete storage location
    """
    try:
        storage_location = StorageLocation.objects.get(id=storage_location_id)
    except DoesNotExist:
        return JsonResponse({"error": "StorageLocation not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(storage_location_to_dict(storage_location), status=200)

    if request.method in ["PUT", "PATCH"]:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        updatable_fields = [
            "zone",
            "shelf",
            "row",
            "column",
            "capacity",
            "is_active",
        ]

        for field in updatable_fields:
            if field in body:
                setattr(storage_location, field, body[field])

        try:
            storage_location.save()
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(storage_location_to_dict(storage_location), status=200)

    if request.method == "DELETE":
        storage_location.delete()
        return JsonResponse({"message": "StorageLocation deleted"}, status=200)

    return HttpResponseNotAllowed(["GET", "PUT", "PATCH", "DELETE"])