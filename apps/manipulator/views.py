import json
import random
import threading
import time as time_module
from datetime import datetime, time
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist, ValidationError

from apps.manipulator.models import ManipulatorLog, Manipulator
from apps.products.models import Product
from apps.storage_location.models import StorageLocation

from utils.pagination_helper import generate_pagination
from .mqtt_manipulator import publish_manipulator_state


manipulator_lock = threading.Lock()

def log_to_dict(log: ManipulatorLog) -> dict:
	"""
	Utility to serialize ManipulatorLog to dict for JSON response.
	"""
	try:
		product_name = log.product.name if log.product else None
	except Exception:
		product_name = "Deleted Product"

	try:
		location_name = _get_pretty_position_name(log.storage_location) if log.storage_location else None
	except Exception:
		location_name = "Deleted Location"

	return {
		"id": str(log.id),
		"timestamp": log.timestamp.isoformat() if log.timestamp else None,
		"max_attempts": log.max_attempts,

		"operation_status": log.operation_status,
		"operation_type": log.operation_type,

		"duration_ms": log.duration_ms,
		"attempt": log.attempt,

		"storage_location": location_name,
		"product": product_name,
		"product_quantity": log.product_quantity if log.product_quantity else None,

		"error_msg": log.error_msg,
	}

def _get_pretty_position_name(storage_location):
	return f"{storage_location.zone} - {storage_location.row} - {storage_location.column}"

def _execute_manipulator_task(op_type, storage_location=None, product=None, product_quantity=None):
	with manipulator_lock:
		return _execute_manipulator_task_internal(op_type, storage_location, product, product_quantity)

def _execute_manipulator_task_internal(op_type, storage_location=None, product=None, product_quantity=None):
	manipulator = Manipulator.objects.first()
	
	if not manipulator:
		raise ValueError("Manipulator not found")

	if manipulator.status == "OFF" and op_type != "START":
		raise ValueError("Manipulator is OFF. Cannot perform operations.")
	
	loc_name = _get_pretty_position_name(storage_location) if storage_location else None

	error_messages = {
		"PICK": 	[f"Failed to find storage location {loc_name}", f"Failed to pick product from storage location {loc_name}", "Product weight mismatch", "Path obstructed to storage location"],
		"PUT": 		[f"Failed to find storage location {loc_name}", f"Failed to put product to storage location {loc_name}", f"Storage location {loc_name} obstructed", "Sensor read error"],
		"MOVE": 	[f"Failed to find storage location {loc_name}", f"Failed to reach destination {loc_name}", f"Path obstructed to storage location {loc_name}"],
	}

	operation_messages = {
		"PICK": 	[f"Trying to pick up product from storage location {loc_name}", "Waiting..."],
		"PUT": 		[f"Trying to put product to storage location {loc_name}", "Waiting..."],
		"MOVE": 	[f"Trying to move to storage location {loc_name}", "Waiting..."],
		"START": 	["Powering on manipulator", "Waiting..."],
		"STOP": 	["Powering off manipulator", "Offline"]
	}

	current_operation = operation_messages.get(op_type, ["Unknown"])

	def _create_log(status, duration, attempt_num, err_msg=None):
		l = ManipulatorLog()
		l.operation_type = op_type
		l.operation_status = status
		l.duration_ms = duration
		l.attempt = attempt_num
		l.error_msg = err_msg
		if storage_location:
			l.storage_location = storage_location
		if product:
			l.product = product
			l.product_quantity = product_quantity
		l.save()
		from apps.manipulator.mqtt_manipulator import publish_new_log
		publish_new_log(log_to_dict(l))
		return l

	final_log = None

	if op_type in ["START", "STOP"]:
		new_status = "ON" if op_type == "START" else "OFF"
		
		publish_manipulator_state(
			manipulator.status,
			_get_pretty_position_name(manipulator.position) if manipulator.position else None,
			current_operation=current_operation[0]
		)
		
		time_module.sleep(1)
		
		final_log = _create_log("SUCCESS", 1000, 1)
		manipulator.update(status=new_status)
	else:
		attempt = 1
		while attempt <= 2:
			duration = random.randint(1500, 5000)
			
			publish_manipulator_state(
				manipulator.status,
				_get_pretty_position_name(manipulator.position) if manipulator.position else None,
				current_operation=f"{current_operation[0]} (Attempt {attempt})"
			)

			time_module.sleep(duration / 1000.0)
			
			if duration > 4500:
				err_msg = random.choice(error_messages.get(op_type, ["Unknown error"]))
				_create_log("FAILURE", duration, attempt, err_msg)

				attempt += 1
				if attempt > 2:
					final_log = _create_log("ABORTED", duration, attempt, err_msg)

					publish_manipulator_state(
						manipulator.status,
						_get_pretty_position_name(manipulator.position) if manipulator.position else None,
						current_operation=f"{current_operation[0]} (ABORTED)"
					)

					time_module.sleep(1)
					break

				publish_manipulator_state(
					manipulator.status,
					_get_pretty_position_name(manipulator.position) if manipulator.position else None,
					current_operation=f"{current_operation[0]} (FAILURE)"
				)

				time_module.sleep(1)
			else:
				final_log = _create_log("SUCCESS", duration, attempt)

				manipulator.update(position=storage_location)
				manipulator.reload()
				publish_manipulator_state(
					manipulator.status,
					_get_pretty_position_name(manipulator.position) if manipulator.position else None,
					current_operation=f"{current_operation[0]} (SUCCESS)"
				)

				time_module.sleep(1)
				break
	
	manipulator.reload()
	publish_manipulator_state(
		manipulator.status,
		_get_pretty_position_name(manipulator.position) if manipulator.position else None,
		current_operation=current_operation[1]
	)

	return final_log


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

		try:
			manipulator = Manipulator.objects.first()
		except DoesNotExist:
			return JsonResponse({"error": "Manipulator not found"}, status=404)

		if manipulator.status == "OFF" and body.get("operation_type") != "START":
			return JsonResponse({"error": "Manipulator is OFF"}, status=400)

		if manipulator.status == "ON" and body.get("operation_type") == "START":
			return JsonResponse({"error": "Manipulator is already ON"}, status=400)

		op_type = body.get("operation_type")

		storage_location_id = body.get("storage_location")
		storage_location = None
		loc_name = None

		product_quantity = body.get("product_quantity")
		product_id = body.get("product")
		product = None


		if storage_location_id:
			try:
				storage_location = StorageLocation.objects.get(id=storage_location_id)
				loc_name = _get_pretty_position_name(storage_location)
			except DoesNotExist:
				return JsonResponse({"error": f"Storage location with id {storage_location_id} not found"}, status=400)
			except ValidationError:
				return JsonResponse({"error": "Invalid Storage location ID format"}, status=400)
				
		if product_id:
			try:
				product = Product.objects.get(id=product_id)
			except DoesNotExist:
				return JsonResponse({"error": f"Product with id {product_id} not found"}, status=400)
			except ValidationError:
				return JsonResponse({"error": "Invalid Product ID format"}, status=400)

		def run_operation():
			_execute_manipulator_task(op_type, storage_location, product, product_quantity)

		threading.Thread(target=run_operation).start()
		
		return JsonResponse({"message": "Operation started in background"}, status=202)

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
		position = _get_pretty_position_name(manipulator.position)
		return JsonResponse({"status": manipulator.status, "position": position})

	if request.method == "PATCH":
		try:
			body = json.loads(request.body.decode("utf-8"))
		except json.JSONDecodeError:
			return JsonResponse({"error": "Invalid JSON"}, status=400)
		
		if body.get("status") == manipulator.status:
			return JsonResponse({"error": f"Manipulator is already {manipulator.status}"}, status=400)
		
		status = body.get("status")
		position = body.get("position")
		
		if status and status in ["ON", "OFF"]:
			manipulator.status = status
		elif status:
			return JsonResponse({"error": "Invalid status. Must be ON or OFF"}, status=400)
		
		if position:
			try:
				storage_location = StorageLocation.objects.get(id=position)
				manipulator.position = storage_location
			except DoesNotExist:
				return JsonResponse({"error": f"Storage location with id {position} not found"}, status=400)
			except ValidationError:
				return JsonResponse({"error": "Invalid Storage location ID format"}, status=400)
		
		manipulator.save()
		position = _get_pretty_position_name(manipulator.position)
		return JsonResponse({"status": manipulator.status, "position": position}, status=200)

	return HttpResponseNotAllowed(["GET", "PATCH"])
