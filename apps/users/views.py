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
    return JsonResponse({"Message": "User registration"}, status=200)


@csrf_exempt
def login(request):
    return JsonResponse({"Message": "User login"}, status=200)