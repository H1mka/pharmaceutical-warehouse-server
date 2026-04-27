import json
from datetime import datetime, time
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist, ValidationError

from apps.manipulator.models import ManipulatorLog, Manipulator
from apps.products.models import Product
from apps.storage_location.models import StorageLocation
from utils.pagination_helper import generate_pagination


def log_to_dict(log: ManipulatorLog) -> dict:
	"""
	Utility to serialize ManipulatorLog to dict for JSON response.
	"""
	try:
		product_id = str(log.product.id) if log.product else None
	except Exception:
		product_id = "Deleted Product"

	try:
		location_id = str(log.storage_location.id) if log.storage_location else None
	except Exception:
		location_id = "Deleted Location"

	return {
		"id": str(log.id),
		"timestamp": log.timestamp.isoformat() if log.timestamp else None,
		"max_attempts": log.max_attempts,

		"operation_status": log.operation_status,
		"operation_type": log.operation_type,

		"duration_ms": log.duration_ms,
		"attempt": log.attempt,

		"storage_location": location_id,
		"product": product_id,
		"product_quantity": log.product_quantity if log.product_quantity else None,

		"error_msg": log.error_msg,
	}


@csrf_exempt
def logs_list_create(request):
	"""
	GET		/control-panel/logs									-> list 10 latest logs
			/control-panel/logs/?limit=10&skip=0				-> list logs with pagination
			/control-panel/logs/?date=YYYY-MM-DD				-> list logs for a specific date
			/control-panel/logs/?start_time=YYYY-MM-DDTHH:MM:SS -> list logs from a specific time
			/control-panel/logs/?end_time=YYYY-MM-DDTHH:MM:SS	-> list logs up to a specific time

	POST	/control-panel/logs									-> add new log
	"""
	if request.method == "GET":
		start_time_str = request.GET.get('start_time')
		end_time_str = request.GET.get('end_time')
		date_str = request.GET.get('date')

		query_filter = {}
		
		if date_str and (start_time_str or end_time_str):
			return JsonResponse({"error": "Cannot use 'date' parameter with 'start_time' or 'end_time' parameters"}, status=400)

		try:
			if date_str:
				target_date = datetime.fromisoformat(date_str).date()
				query_filter['timestamp__gte'] = datetime.combine(target_date, time.min)
				query_filter['timestamp__lte'] = datetime.combine(target_date, time.max)
			else:
				start_dt = None
				end_dt = None
				if start_time_str:
					start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
					query_filter['timestamp__gte'] = start_dt
				if end_time_str:
					end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
					query_filter['timestamp__lte'] = end_dt

				if start_dt and end_dt and start_dt > end_dt:
					return JsonResponse({"error": "start_time cannot be later than end_time"}, status=400)
		except ValueError:
			return JsonResponse({"error": "Invalid date or time format. Please use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"}, status=400)

		try:
			pagination_data, skip = generate_pagination(request, ManipulatorLog.objects.count())
		except ValueError as e:
			return JsonResponse({
							"success": False,
							"data": [],
							"error": str(e),
					}, status=400)
		except Exception as e:
			return JsonResponse({"success": False, "error": "Unknown error"}, status=500)

		# sort logs from new to old
		logs = ManipulatorLog.objects(**query_filter).order_by('-timestamp').skip(skip).limit(pagination_data['page_size'])
		data = [log_to_dict(log) for log in logs]

		return JsonResponse(
            {
                "success": True,
                "data": data,
                "extra": pagination_data,
            },
            status=200,
        )

	# ============================================ #
	# ================== POST ==================== #
	# ============================================ #

	if request.method == "POST":
		try:
			body = json.loads(request.body.decode("utf-8"))
		except json.JSONDecodeError:
			return JsonResponse({"error": "Invalid JSON"}, status=400)

		if Manipulator.objects.first().status == "OFF" and body.get("operation_type") != "START":
			return JsonResponse({"error": "Manipulator is OFF"}, status=400)

		if Manipulator.objects.first().status == "ON" and body.get("operation_type") == "START":
			return JsonResponse({"error": "Manipulator is already ON"}, status=400)

		if body.get("operation_type") == "START":
			Manipulator.objects.first().update(status="ON")
		elif body.get("operation_type") == "STOP":
			Manipulator.objects.first().update(status="OFF")

		log = ManipulatorLog()
		
		log.operation_status = body.get("operation_status")
		log.operation_type = body.get("operation_type")
		
		log.duration_ms = body.get("duration_ms")
		log.attempt = body.get("attempt")


		storage_location_id = body.get("storage_location")
		if storage_location_id:
			try:
				storage_location = StorageLocation.objects.get(id=storage_location_id)
				log.storage_location = storage_location
				Manipulator.objects.first().update(position=storage_location)
			except DoesNotExist:
				return JsonResponse({"error": f"Storage location with id {storage_location_id} not found"}, status=400)
			except ValidationError:
				return JsonResponse({"error": "Invalid Storage location ID format"}, status=400)
				
		product_id = body.get("product")
		if product_id:
			try:
				product = Product.objects.get(id=product_id)
				log.product = product
				log.product_quantity = body.get("product_quantity")
			except DoesNotExist:
				return JsonResponse({"error": f"Product with id {product_id} not found"}, status=400)
			except ValidationError:
				return JsonResponse({"error": "Invalid Product ID format"}, status=400)

		log.error_msg = body.get("error_msg")

		try:
			log.save()
		except ValidationError as e:
			return JsonResponse({"error": str(e)}, status=400)

		return JsonResponse(log_to_dict(log), status=201)

	return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def log_detail(request, log_id: str):
	"""
	GET	 	/control-panel/logs/<id> -> get one log entry details
	DELETE 	/control-panel/logs/<id> -> delete a log entry
	"""
	try:
		log = ManipulatorLog.objects.get(id=log_id)
	except DoesNotExist:
		return JsonResponse({"error": "Log entry not found"}, status=404)
	except ValidationError:
		 return JsonResponse({"error": "Invalid Log ID format"}, status=400)

	if request.method == "GET":
		return JsonResponse(log_to_dict(log), status=200)

	if request.method == "DELETE":
		log.delete()
		return JsonResponse({"message": "Log entry deleted"}, status=200)

	return HttpResponseNotAllowed(["GET", "DELETE"])


@csrf_exempt
def manipulator_detail(request):
	"""
	GET 	/control-panel/manipulator-state -> get manipulator state
	PATCH 	/control-panel/manipulator-state -> update manipulator state
	"""

	try:
		manipulator = Manipulator.objects.first()
	except DoesNotExist:
		return JsonResponse({"error": "Manipulator not found"}, status=404)
	except ValidationError:
		return JsonResponse({"error": "Invalid Manipulator ID format"}, status=400)

	if request.method == "GET":
		return JsonResponse({"status": manipulator.status, "position": str(manipulator.position.id)}, status=200)

	if request.method == "PATCH":
		try:
			body = json.loads(request.body.decode("utf-8"))
		except json.JSONDecodeError:
			return JsonResponse({"error": "Invalid JSON"}, status=400)
		
		if body.get("status") == manipulator.status:
			return JsonResponse({"error": f"Manipulator is already {manipulator.status}"}, status=400)
		
		status = body.get("status")
		position = body.get("position")
		
		if status:
			manipulator.status = status
		
		if position:
			try:
				storage_location = StorageLocation.objects.get(id=position)
				manipulator.position = storage_location
			except DoesNotExist:
				return JsonResponse({"error": f"Storage location with id {position} not found"}, status=400)
			except ValidationError:
				return JsonResponse({"error": "Invalid Storage location ID format"}, status=400)
		
		manipulator.save()
		return JsonResponse({"status": manipulator.status, "position": str(manipulator.position.id)}, status=200)

	return HttpResponseNotAllowed(["GET", "PATCH"])