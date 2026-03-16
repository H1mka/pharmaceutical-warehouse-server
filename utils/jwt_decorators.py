from django.http import JsonResponse
from functools import wraps
from .jwt_helper import verify_jwt

def role_required(roles):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            user = verify_jwt(request)

            if not user:
                return JsonResponse({"error": "Unauthorized"}, status=401)

            if user.role not in roles:
                return JsonResponse({"error": "Forbidden, missing permissions"}, status=403)

            request.user = user

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator