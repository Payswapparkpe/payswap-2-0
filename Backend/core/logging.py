import json
import logging
import threading
from datetime import UTC, datetime

_local = threading.local()


def set_log_context(*, request_id="", user_id="", ip=""):
    _local.request_id = request_id or ""
    _local.user_id = str(user_id or "")
    _local.ip = ip or ""


def get_log_context() -> dict:
    return {
        "request_id": getattr(_local, "request_id", "") or "",
        "user_id": getattr(_local, "user_id", "") or "",
        "ip": getattr(_local, "ip", "") or "",
    }


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        ctx = get_log_context()
        record.request_id = ctx["request_id"]
        record.user_id = ctx["user_id"]
        record.ip = ctx["ip"]
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "") or "",
            "user_id": getattr(record, "user_id", "") or "",
            "ip": getattr(record, "ip", "") or "",
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
