from django.utils import timezone

from notifications.catalog import TRANSACTIONAL_SMS_TEMPLATES
from notifications.email_service import EmailService
from notifications.sms_service import SmsService

from .models import InboxMessage, InboxThread, Notification, NotificationPreference

# Security/account-integrity messages are delivered regardless of opt-ins.
ALWAYS_ON_TEMPLATES = frozenset(
    {"verification_code", "login_new_session", "session_revoked", "password_reset"}
)


def _preference(user) -> NotificationPreference:
    pref = getattr(user, "notification_preference", None)
    if pref is None:
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
    return pref


class NotificationService:
    @staticmethod
    def notify(
        *,
        user,
        title,
        body,
        url="",
        email=True,
        sms=False,
        template="generic_notice",
        context=None,
        request=None,
        idempotency_key="",
    ):
        del request  # reserved for callers; delivery logs carry correlation
        safe_body = body if template in ALWAYS_ON_TEMPLATES else (body or title)[:240]
        if template not in ALWAYS_ON_TEMPLATES and context and context.get("reason"):
            safe_body = f"{title}. Sign in to view details."
        notification = Notification.objects.create(user=user, title=title, body=safe_body, url=url)
        payload = {
            "user": user,
            "title": title,
            "body": body,
            "action_url": url,
            "action_label": "Open record",
            **(context or {}),
        }
        pref = _preference(user)
        always_on = template in ALWAYS_ON_TEMPLATES
        transactional_sms = template in TRANSACTIONAL_SMS_TEMPLATES
        fail_silently = always_on
        if email and getattr(user, "email", "") and (always_on or pref.email_enabled):
            EmailService.send(
                to=user.email,
                template=template,
                context=payload,
                fail_silently=fail_silently,
                idempotency_key=idempotency_key,
            )
        send_sms = sms or transactional_sms or always_on
        if send_sms and getattr(user, "mobile", "") and (always_on or transactional_sms or pref.sms_enabled):
            SmsService.send(
                to=user.mobile,
                template=template,
                context=payload,
                fail_silently=fail_silently,
                idempotency_key=idempotency_key,
            )
        return notification

    @staticmethod
    def unread_count(user) -> int:
        if not user or not user.is_authenticated:
            return 0
        return Notification.objects.filter(user=user, read_at__isnull=True).count()

    @staticmethod
    def mark_read(notification):
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])


class MessagingService:
    @staticmethod
    def start(*, actor, recipient, subject: str, body: str) -> InboxThread:
        if actor.id == recipient.id:
            from django.core.exceptions import ValidationError

            raise ValidationError("You cannot message yourself.")
        thread = InboxThread.objects.create(subject=subject.strip(), created_by=actor)
        thread.participants.add(actor, recipient)
        InboxMessage.objects.create(thread=thread, sender=actor, body=body.strip())
        NotificationService.notify(
            user=recipient,
            title=subject.strip(),
            body=body.strip()[:240],
            url=_inbox_url(recipient, thread.pk),
            template="generic_notice",
        )
        return thread

    @staticmethod
    def reply(*, actor, thread: InboxThread, body: str) -> InboxMessage:
        if actor not in thread.participants.all():
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You cannot reply to this conversation.")
        message = InboxMessage.objects.create(thread=thread, sender=actor, body=body.strip())
        thread.save(update_fields=["updated_at"])
        for user in thread.participants.exclude(pk=actor.pk):
            NotificationService.notify(
                user=user,
                title=f"Reply: {thread.subject}",
                body=body.strip()[:240],
                url=_inbox_url(user, thread.pk),
            )
        return message

    @staticmethod
    def threads_for(user):
        if not user or not user.is_authenticated:
            return InboxThread.objects.none()
        return InboxThread.objects.filter(participants=user).prefetch_related("participants", "messages")


def _inbox_url(user, thread_id: int) -> str:
    if user.user_type == user.UserType.ADMIN:
        return f"/administration/messages/{thread_id}/"
    if user.user_type == user.UserType.EMPLOYEE:
        return f"/employee/messages/{thread_id}/"
    return f"/merchant/messages/{thread_id}/"
