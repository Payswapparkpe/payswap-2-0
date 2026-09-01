import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from accounts.models import User

UserModel = get_user_model()


def api_error(message, *, status=400, **extra):
    payload = {"error": message, **extra}
    return JsonResponse(payload, status=status)


def parse_json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Invalid JSON body.")


class JsonView(View):
    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except ValidationError as exc:
            return api_error(" ".join(exc.messages), status=400)
        except PermissionDenied as exc:
            return api_error(str(exc) or "Permission denied.", status=403)

    @staticmethod
    def ok(data=None, *, status=200):
        return JsonResponse(data or {}, status=status)


class MerchantRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return api_error("Authentication required.", status=401)
        if user.user_type != User.UserType.MERCHANT:
            return api_error(
                "Corporate partner access only.",
                status=403,
                use_staff_portal=True,
                staff_login_url="/login/",
            )
        return super().dispatch(request, *args, **kwargs)
