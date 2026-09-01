from dataclasses import dataclass, field

from django.conf import settings

PRODUCT_NAME = "PayswapHub"

OTP_SMS_TEMPLATES = frozenset({"verification_code", "login_new_session", "password_reset"})
TRANSACTIONAL_SMS_TEMPLATES = frozenset(
    {
        "order_submitted",
        "order_approved",
        "order_rejected",
        "order_changes_requested",
        "order_cancelled",
        "agreement_ready",
        "agreement_executed",
        "agreement_esign_failed",
        "application_approved",
        "application_rejected",
        "onboarding_clarification",
        "document_rejected",
        "document_replacement",
    }
)


def _dlt_id(key: str) -> str:
    mapping = getattr(settings, "KALEYRA_DLT_TEMPLATES", {}) or {}
    return str(mapping.get(key) or "")


@dataclass(frozen=True)
class NotificationTemplate:
    key: str
    email_subject: str
    sms_body: str = "{{ title }}: {{ body }}"
    sms_type: str = "TXN"
    dlt_template_id: str = field(default="")

    @property
    def resolved_dlt_id(self) -> str:
        return self.dlt_template_id or _dlt_id(self.key)


TEMPLATES = {
    spec.key: spec
    for spec in (
        NotificationTemplate(
            "verification_code",
            "Your Payswap email verification code",
            "Your one time password is {{ code }}. Please do not share this OTP any one. Powered by PAYSWAP",
            sms_type="OTP",
            dlt_template_id="1007141008198087301",
        ),
        NotificationTemplate(
            "welcome",
            "Welcome to PayswapHub",
            "Welcome to PayswapHub. Sign in to continue onboarding.",
        ),
        NotificationTemplate(
            "password_reset",
            "Reset your PayswapHub password",
            "Reset your PayswapHub password: {{ action_url }} — link expires soon.",
            sms_type="OTP",
        ),
        NotificationTemplate(
            "login_new_session",
            "New sign-in on your account",
            "New sign-in detected. If this was not you, review sessions.",
            sms_type="OTP",
        ),
        NotificationTemplate(
            "session_revoked",
            "A session was revoked",
            "A session on your account was revoked.",
        ),
        NotificationTemplate(
            "onboarding_clarification",
            "Action required on your application",
            "Action required on application {{ reference }}. Sign in to update it.",
        ),
        NotificationTemplate(
            "application_approved",
            "Your merchant application was approved",
            "Application {{ reference }} was approved.",
        ),
        NotificationTemplate(
            "application_rejected",
            "Your merchant application was not approved",
            "Application {{ reference }} was not approved.",
        ),
        NotificationTemplate(
            "document_rejected",
            "A document was rejected",
            "A document was rejected. Sign in to replace it.",
        ),
        NotificationTemplate(
            "document_replacement",
            "Please replace a submitted document",
            "Please replace a submitted document.",
        ),
        NotificationTemplate(
            "agreement_ready",
            "Your service agreement is ready to review",
            "Your agreement {{ reference }} is ready to review.",
        ),
        NotificationTemplate(
            "agreement_executed",
            "Your agreement is in force",
            "Agreement {{ reference }} is in force. Your account is active.",
        ),
        NotificationTemplate(
            "agreement_esign_failed",
            "Agreement eSign did not complete",
            "eSign for agreement {{ reference }} did not complete. Sign in to retry.",
        ),
        NotificationTemplate(
            "order_submitted",
            "Your purchase order was submitted",
            "Order {{ reference }} was submitted for review.",
        ),
        NotificationTemplate(
            "order_approved",
            "Your purchase order was approved",
            "Order {{ reference }} was approved.",
        ),
        NotificationTemplate(
            "order_rejected",
            "Your purchase order was rejected",
            "Order {{ reference }} was rejected.",
        ),
        NotificationTemplate(
            "order_changes_requested",
            "Changes requested on your order",
            "Changes were requested on order {{ reference }}. Sign in to update it.",
        ),
        NotificationTemplate(
            "order_cancelled",
            "Your purchase order was cancelled",
            "Order {{ reference }} was cancelled.",
        ),
        NotificationTemplate(
            "generic_notice",
            "{{ title|default:'Account notice' }}",
            "{{ title }}: {{ body }}",
            sms_type="MKT",
        ),
    )
}

MAIL_TEMPLATES = {key: spec.email_subject for key, spec in TEMPLATES.items()}
