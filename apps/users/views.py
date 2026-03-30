import datetime
import json

from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import NotUniqueError, ValidationError
from utils.jwt_helper import generate_jwt_for_user
from .models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password


def _user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@csrf_exempt
def register(request):
    """
    POST /auth/register
    Body JSON:
      - username (required)
      - first_name (required)
      - last_name (required)
      - password (required)  # stored as-is (NOT hashed)
      - role (optional): "admin" | "pharmacist"
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        body = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    username = body.get("username")
    first_name = body.get("first_name")
    last_name = body.get("last_name")
    password = body.get("password")
    role = body.get("role")

    missing = [
        field_name
        for field_name, value in [
            ("username", username),
            ("first_name", first_name),
            ("last_name", last_name),
            ("password", password),
        ]
        if not value
    ]
    if missing:
        return JsonResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"}, status=400
        )

    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        password=make_password(password),  # explicitly NOT hashed by request
    )
    if role is not None:
        user.role = role

    try:
        user.save()
    except NotUniqueError:
        return JsonResponse({"error": "Username already exists"}, status=400)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    token = generate_jwt_for_user(user)
    return JsonResponse({"user": _user_to_dict(user), "token": token}, status=201)


@csrf_exempt
def login(request):
    if request.method != "POST":
      return HttpResponseNotAllowed(["POST"])

    try:
        body = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    login = body.get("login")
    password = body.get("password")

    user = User.objects(username=login).first()
  
    if not user or not check_password(password, user.password):
      return JsonResponse({"message": "Invalid credentials"}, status=400)
    
    token = generate_jwt_for_user(user)

    return JsonResponse({"user": _user_to_dict(user), "token": token}, status=200)