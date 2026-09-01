import json
import logging

from django.http import HttpResponse
from django.test import RequestFactory

from core.logging import JsonFormatter, RequestContextFilter, set_log_context
from core.middleware import RequestIDMiddleware


def test_json_formatter_includes_request_context():
    set_log_context(request_id="rid-1", user_id="42", ip="127.0.0.1")
    record = logging.LogRecord(
        name="payswap.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    RequestContextFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "rid-1"
    assert payload["user_id"] == "42"
    assert payload["message"] == "hello"


def test_request_id_header_is_echoed(admin_user):
    captured = {}

    def inner(request):
        captured["request_id"] = request.request_id
        return HttpResponse("ok")

    factory = RequestFactory()
    request = factory.get("/administration/", HTTP_X_REQUEST_ID="abc123abc123")
    request.user = admin_user
    response = RequestIDMiddleware(inner)(request)
    assert response["X-Request-ID"] == "abc123abc123"
    assert captured["request_id"] == "abc123abc123"
