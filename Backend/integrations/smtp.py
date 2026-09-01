import ssl

import certifi
from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property


class SesSmtpEmailBackend(EmailBackend):
    """AWS SES SMTP with certifi CA bundle (macOS Python.org SSL fix)."""

    @cached_property
    def ssl_context(self):
        return ssl.create_default_context(cafile=certifi.where())
