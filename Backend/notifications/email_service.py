import hashlib
import logging
import uuid
from email.utils import formataddr, parseaddr
from types import SimpleNamespace

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.template.loader import render_to_string

from audit.services import AuditService
from notifications.catalog import TEMPLATES
from notifications.models import DeliveryStatus, EmailLog
from notifications.payload import hydrate_context, protect_context, serialize_context

logger = logging.getLogger("payswap.notifications")


def _body_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()


def _idempotency_key(template: str, recipient: str, context: dict) -> str:
    payload = serialize_context(context)
    blob = f"{template}|{recipient}|{sorted(payload.items())}"
    return hashlib.sha256(blob.encode()).hexdigest()[:64]


class EmailService:
    FROM_NAME = "Payswap"
    OTP_TEMPLATES = frozenset({"verification_code"})
    # Auth mail must use the verified support@ sender — noreply@ SES identity rejects locally.
    AUTH_EMAIL_TEMPLATES = frozenset({"verification_code", "password_reset"})

    @staticmethod
    def branded_from_email(*, template: str = "") -> str:
        if template in EmailService.AUTH_EMAIL_TEMPLATES:
            raw = getattr(settings, "OTP_FROM_EMAIL", "") or getattr(settings, "DEFAULT_FROM_EMAIL", "")
        else:
            raw = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
        _name, addr = parseaddr(raw)
        if not addr:
            addr = "support@payswap.in" if template in EmailService.OTP_TEMPLATES else "noreply@payswap.in"
        display = _name or EmailService.FROM_NAME
        return formataddr((display, addr))

    @staticmethod
    def reply_to_for(*, template: str = "") -> list[str]:
        if template in EmailService.AUTH_EMAIL_TEMPLATES:
            addr = getattr(settings, "OTP_REPLY_TO_EMAIL", "") or "support@payswap.in"
            return [addr]
        grievance = getattr(settings, "GRIEVANCE_EMAIL", "") or ""
        if grievance:
            return [grievance]
        return []

    @staticmethod
    def absolute_url(path: str = "") -> str:
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        if not path:
            return base
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{base}{path}"

    @classmethod
    def _payload(cls, context: dict) -> dict:
        payload = {
            "product": EmailService.FROM_NAME,
            "support_url": cls.absolute_url("/merchant/"),
            "home_url": cls.absolute_url("/"),
            "preference_url": cls.absolute_url("/merchant/profile/"),
            "unsubscribe_url": cls.absolute_url("/merchant/profile/"),
            "grievance_address": getattr(settings, "GRIEVANCE_POSTAL_ADDRESS", "") or "",
            "grievance_email": getattr(settings, "GRIEVANCE_EMAIL", "") or "",
            "grievance_officer": getattr(settings, "GRIEVANCE_OFFICER_NAME", "") or "",
            "legal_entity": getattr(settings, "LEGAL_ENTITY_NAME", "") or EmailService.FROM_NAME,
            "otp_expiry_minutes": max(1, int(getattr(settings, "OTP_EXPIRY_SECONDS", 300) // 60)),
            "support_email": getattr(settings, "OTP_REPLY_TO_EMAIL", "") or "support@payswap.in",
            **context,
        }
        if payload.get("action_url"):
            payload["action_url"] = cls.absolute_url(payload["action_url"])
        user = payload.get("user")
        if getattr(user, "email", None):
            payload.setdefault("email", user.email)
        payload.setdefault("email", "")
        if user is None:
            payload["user"] = SimpleNamespace(email=payload["email"], name="")
        return payload

    @classmethod
    def render(cls, template: str, context: dict) -> tuple[str, str, str]:
        if template not in TEMPLATES:
            raise ValueError(f"Unknown email template: {template}")
        payload = cls._payload(hydrate_context(serialize_context(context)))
        html = render_to_string(f"emails/{template}.html", payload)
        text = render_to_string(f"emails/{template}.txt", payload)
        footer = render_to_string("emails/_footer.txt", payload)
        text = f"{text.rstrip()}\n\n{footer.strip()}\n"
        subject = Template(TEMPLATES[template].email_subject).render(Context(payload))
        return html, text, subject

    @classmethod
    def send_login_alert(cls, *, user, ip_address="", user_agent="", new_device=False):
        prefix = {
            user.UserType.ADMIN: "/administration",
            user.UserType.EMPLOYEE: "/employee",
            user.UserType.MERCHANT: "/merchant",
        }.get(user.user_type, "/merchant")
        return cls.send(
            to=user.email,
            template="login_new_session",
            context={
                "user": user,
                "ip_address": ip_address or "unknown",
                "user_agent": (user_agent or "unknown")[:255],
                "action_url": f"{prefix}/sessions/",
                "new_device": new_device,
            },
            fail_silently=True,
        )

    @classmethod
    def send(
        cls,
        *,
        to: str,
        template: str,
        context: dict,
        fail_silently: bool = False,
        sensitive: bool = False,
        idempotency_key: str = "",
    ):
        from notifications.tasks import enqueue, send_email_task  # circular: tasks import EmailService

        payload = protect_context(context) if sensitive else serialize_context(context)
        user = context.get("user")
        key = idempotency_key or _idempotency_key(template, to, context)
        log = cls._queue_log(
            to=to,
            template=template,
            user=user if getattr(user, "pk", None) else None,
            idempotency_key=key,
            body_hash=_body_hash(str(payload)),
        )
        if log.status == DeliveryStatus.SENT:
            return 0
        enqueue(send_email_task, log.pk, payload, fail_silently)
        return 1

    @classmethod
    def _queue_log(cls, *, to, template, user, idempotency_key, body_hash):
        try:
            with transaction.atomic():
                return EmailLog.objects.create(
                    public_id=uuid.uuid4().hex[:20],
                    user=user if getattr(user, "pk", None) else None,
                    recipient=to,
                    template_key=template,
                    provider="ses",
                    status=DeliveryStatus.QUEUED,
                    idempotency_key=idempotency_key,
                    body_hash=body_hash,
                )
        except IntegrityError:
            return EmailLog.objects.get(provider="ses", idempotency_key=idempotency_key)

    @classmethod
    def deliver(cls, *, to: str, template: str, context: dict, fail_silently: bool = False, log=None):
        html, text, subject = cls.render(template, context)
        if log is not None:
            log.subject = subject[:200]
            log.body_hash = _body_hash(text)
            log.attempts = (log.attempts or 0) + 1
            log.save(update_fields=["subject", "body_hash", "attempts", "updated_at"])
        try:
            message = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=cls.branded_from_email(template=template),
                to=[to],
                reply_to=cls.reply_to_for(template=template) or None,
            )
            message.attach_alternative(html, "text/html")
            sent = message.send(fail_silently=False)
            if log is not None:
                log.status = DeliveryStatus.SENT
                log.provider_message_id = getattr(message, "extra_headers", {}).get("Message-ID", "") or ""
                log.last_error = ""
                log.save(update_fields=["status", "provider_message_id", "last_error", "updated_at"])
                AuditService.record(
                    actor=log.user,
                    action="notification.email_sent",
                    resource_type="user",
                    resource_id=str(log.user_id or to),
                    after={"template": template, "status": "sent"},
                )
            return sent
        except Exception as exc:
            logger.exception("Email delivery failed for %s template %s", to, template)
            if log is not None:
                log.status = DeliveryStatus.FAILED
                log.last_error = str(exc)[:2000]
                log.save(update_fields=["status", "last_error", "updated_at"])
                AuditService.record(
                    actor=log.user,
                    action="notification.email_failed",
                    resource_type="user",
                    resource_id=str(log.user_id or to),
                    result="failure",
                    after={"template": template},
                    reason=str(exc)[:500],
                )
            if fail_silently:
                return 0
            raise


MailService = EmailService
