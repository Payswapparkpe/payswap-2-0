import json

from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """Liveness: the process is up and can serve requests."""
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request):
    """Readiness: database and cache reachable. 503 when any dependency is down."""
    checks = {}

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    try:
        probe = json.dumps(cache.get_or_set("readyz:probe", "ok", timeout=10))
        checks["cache"] = probe == '"ok"'
    except Exception:
        checks["cache"] = False

    healthy = all(checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )
