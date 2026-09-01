import logging

from django.conf import settings

from core.celery import app as celery_app
from notifications.models import DeliveryStatus, EmailLog, SmsLog

logger = logging.getLogger("payswap.notifications")


def enqueue(task, *args):
    # Eager execution is the local default (no worker). Production must run a
    # Celery worker; DEBUG alone does not decide this — CELERY_TASK_ALWAYS_EAGER does.
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return task.apply(args=args)
    try:
        return task.delay(*args)
    except Exception:
        logger.exception("Celery broker unavailable for %s", getattr(task, "name", task))
        if getattr(settings, "IS_PRODUCTION", False):
            raise
        return task.apply(args=args)


@celery_app.task(
    bind=True,
    name="notifications.send_email",
    autoretry_for=(OSError, TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
    acks_late=True,
)
def send_email_task(self, log_id, context: dict, fail_silently: bool = False):
    from notifications.email_service import EmailService

    log = EmailLog.objects.filter(pk=log_id).first()
    if log is None:
        return None
    if log.status == DeliveryStatus.SENT:
        return 0
    return EmailService.deliver(
        to=log.recipient,
        template=log.template_key,
        context=context,
        fail_silently=fail_silently,
        log=log,
    )


@celery_app.task(
    bind=True,
    name="notifications.send_sms",
    autoretry_for=(OSError, TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
    acks_late=True,
)
def send_sms_task(self, log_id, context: dict, fail_silently: bool = True):
    from notifications.sms_service import SmsService

    log = SmsLog.objects.filter(pk=log_id).first()
    if log is None:
        return None
    if log.status == DeliveryStatus.SENT:
        return None
    return SmsService.deliver(
        to=log.recipient,
        template=log.template_key,
        context=context,
        fail_silently=fail_silently,
        log=log,
    )
