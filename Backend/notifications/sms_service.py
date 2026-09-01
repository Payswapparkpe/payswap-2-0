import hashlib
import logging
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.template import Context, Template

from audit.services import AuditService
from integrations.kaleyra import KaleyraClient, KaleyraError
from notifications.catalog import TEMPLATES
from notifications.models import DeliveryStatus, SmsLog
from notifications.payload import hydrate_context, protect_context, serialize_context

logger = logging.getLogger("payswap.notifications")


def _truncate_words(text: str, limit: int = 160) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    clipped = compact[: limit - 3]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return f"{clipped.rstrip()}..."


def _idempotency_key(template: str, recipient: str, context: dict) -> str:
    payload = serialize_context(context)
    blob = f"{template}|{recipient}|{sorted(payload.items())}"
    return hashlib.sha256(blob.encode()).hexdigest()[:64]


class SmsService:
    @staticmethod
    def client() -> KaleyraClient:
        return KaleyraClient(
            sid=getattr(settings, "KALEYRA_SID", ""),
            api_key=getattr(settings, "KALEYRA_API_KEY", ""),
            sender=getattr(settings, "KALEYRA_SENDER", ""),
            base_url=getattr(settings, "KALEYRA_BASE_URL", "https://api.in.kaleyra.io"),
        )

    @classmethod
    def render(cls, template: str, context: dict) -> str:
        if template not in TEMPLATES:
            raise ValueError(f"Unknown SMS template: {template}")
        spec = TEMPLATES[template]
        body = Template(spec.sms_body).render(Context(hydrate_context(context)))
        address = getattr(settings, "GRIEVANCE_POSTAL_ADDRESS", "") or ""
        rendered = " ".join(body.split())
        if spec.sms_type != "OTP" and address and len(rendered) < 120:
            rendered = f"{rendered} {address}"
        return _truncate_words(rendered, 160)

    @classmethod
    def send(
        cls,
        *,
        to: str,
        template: str,
        context: dict,
        fail_silently: bool = True,
        sensitive: bool = False,
        idempotency_key: str = "",
    ):
        from notifications.tasks import enqueue, send_sms_task  # circular: tasks import SmsService

        payload = protect_context(context) if sensitive else serialize_context(context)
        user = context.get("user")
        key = idempotency_key or _idempotency_key(template, to, context)
        log = cls._queue_log(
            to=to,
            template=template,
            user=user if getattr(user, "pk", None) else None,
            idempotency_key=key,
        )
        if log.status == DeliveryStatus.SENT:
            return True
        enqueue(send_sms_task, log.pk, payload, fail_silently)
        return True

    @classmethod
    def _queue_log(cls, *, to, template, user, idempotency_key):
        try:
            with transaction.atomic():
                return SmsLog.objects.create(
                    public_id=uuid.uuid4().hex[:20],
                    user=user if getattr(user, "pk", None) else None,
                    recipient=to,
                    template_key=template,
                    provider="kaleyra",
                    status=DeliveryStatus.QUEUED,
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:
            return SmsLog.objects.get(provider="kaleyra", idempotency_key=idempotency_key)

    @classmethod
    def deliver(cls, *, to: str, template: str, context: dict, fail_silently: bool = True, log=None):
        client = cls.client()
        if not client.configured:
            if log is not None:
                log.status = DeliveryStatus.FAILED
                log.last_error = "Kaleyra SMS is not configured."
                log.save(update_fields=["status", "last_error", "updated_at"])
            logger.warning("SMS skipped: Kaleyra is not configured (template %s)", template)
            return None
        spec = TEMPLATES.get(template)
        try:
            body = cls.render(template, context)
            if log is not None:
                log.body_preview = body[:160]
                log.attempts = (log.attempts or 0) + 1
                log.save(update_fields=["body_preview", "attempts", "updated_at"])
            data = client.send_sms(
                to=to,
                body=body,
                sms_type=getattr(spec, "sms_type", "TXN") if spec else "TXN",
                template_id=spec.resolved_dlt_id if spec else "",
                entity_id=getattr(settings, "KALEYRA_ENTITY_ID", "") or "",
            )
            message_id = ""
            if isinstance(data, dict):
                message_id = str(data.get("id") or "")
                sms_nodes = data.get("sms") or []
                if sms_nodes and isinstance(sms_nodes, list):
                    message_id = str(sms_nodes[0].get("message_id") or message_id)
            if log is not None:
                log.status = DeliveryStatus.SENT
                log.provider_message_id = message_id
                log.last_error = ""
                log.save(update_fields=["status", "provider_message_id", "last_error", "updated_at"])
                AuditService.record(
                    actor=log.user,
                    action="notification.sms_sent",
                    resource_type="user",
                    resource_id=str(log.user_id or to),
                    after={"template": template, "status": "sent"},
                )
            return data
        except KaleyraError as exc:
            logger.exception("SMS delivery failed for %s template %s", to, template)
            if log is not None:
                log.status = DeliveryStatus.FAILED
                log.last_error = str(exc)[:2000]
                log.save(update_fields=["status", "last_error", "updated_at"])
                AuditService.record(
                    actor=log.user,
                    action="notification.sms_failed",
                    resource_type="user",
                    resource_id=str(log.user_id or to),
                    result="failure",
                    reason=str(exc)[:500],
                )
            if fail_silently:
                return None
            raise
