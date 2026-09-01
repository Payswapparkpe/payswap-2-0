from core.ip import client_ip

from .models import AuditEvent

REDACT_KEYS = {
    "password",
    "otp",
    "code",
    "code_hash",
    "voucher_code",
    "voucher_codes",
    "codes",
    "account_number",
    "secret",
    "api_secret",
    "client_secret",
    "webhook_secret",
    "authorization",
    "x-api-key",
    "token",
    "pan",
    "gstin",
    "aadhaar",
    "document_number",
    "ifsc",
    "cin",
    "mobile",
    "email",
    "mpin",
    "recovery_code",
}


def redact(value):
    if isinstance(value, dict):
        return {
            key: "********" if key.lower() in REDACT_KEYS else redact(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class AuditService:
    @staticmethod
    def record(
        *,
        actor=None,
        action,
        resource_type="",
        resource_id="",
        result="success",
        reason="",
        before=None,
        after=None,
        request=None,
    ) -> AuditEvent:
        ip = None
        request_id = ""
        user_agent = ""
        if request is not None:
            ip = client_ip(request) or None
            request_id = getattr(request, "request_id", "")
            user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
        return AuditEvent.objects.create(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id or ""),
            result=result,
            reason=reason,
            before=redact(before) if before is not None else None,
            after=redact(after) if after is not None else None,
            ip_address=ip,
            request_id=request_id,
            user_agent=user_agent,
        )
