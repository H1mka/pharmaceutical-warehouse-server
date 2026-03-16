import os
import datetime
import jwt

from django.http import JsonResponse
from functools import wraps
from apps.users.models import User

def generate_jwt_for_user(user: User) -> str:
  now = datetime.datetime.utcnow()
  payload = {
      "id": str(user.id),
      "username": user.username,
      "role": user.role,
      "iat": int(now.timestamp()),
      "exp": int((now + datetime.timedelta(days=7)).timestamp()),
  }
  return jwt.encode(payload, os.getenv('JWT_SECRET'), algorithm="HS256")

def verify_jwt(request):
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return None

    try:
        token = auth_header.split(" ")[1]

        payload = jwt.decode(
            token,
            os.getenv('JWT_SECRET'),
            algorithms=["HS256"]
        )

        user = User.objects(id=payload["id"]).first()

        return user

    except Exception:
        return None