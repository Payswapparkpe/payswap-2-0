from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views import View

from .mixins import JsonView


class CsrfView(View):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return JsonView.ok({"csrfToken": get_token(request)})
