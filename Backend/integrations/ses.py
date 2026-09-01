from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address


class SesEmailBackend(BaseEmailBackend):
    """Send mail through Amazon SES. Falls back to SMTP settings when boto3 is absent."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        try:
            import boto3
        except ImportError:
            from django.core.mail.backends.smtp import EmailBackend

            return EmailBackend().send_messages(email_messages)
        client = boto3.client(
            "ses",
            region_name=getattr(settings, "AWS_SES_REGION", "ap-south-1"),
            aws_access_key_id=settings.AWS_SES_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SES_SECRET_ACCESS_KEY or None,
        )
        sent = 0
        for message in email_messages:
            from_email = sanitize_address(message.from_email, message.encoding)
            client.send_raw_email(
                Source=from_email,
                Destinations=message.recipients(),
                RawMessage={"Data": message.message().as_bytes(linesep="\r\n")},
            )
            sent += 1
        return sent
