import hashlib
import hmac
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    key = (getattr(settings, "FIELD_ENCRYPTION_KEY", "") or "").encode()
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is required for encrypted fields.")
    # Fernet keys are 32 url-safe base64-encoded bytes (44 characters). Do not
    # pad passphrases — that produces a weak, deterministic key.
    if len(key) != 44:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY must be a Fernet key from cryptography.fernet.Fernet.generate_key()."
        )
    return Fernet(key)


def encrypt_text(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_text(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        logger.warning(
            "Encrypted field could not be decrypted; the key may be wrong or the value is corrupt."
        )
        return ""


def lookup_hash(value: str) -> str:
    """Keyed HMAC-SHA256 for deterministic lookup of sensitive identifiers.

    Keyed with FIELD_ENCRYPTION_KEY so the digest is unforgeable without the
    field key and rotates with it (same operational lifetime as the encrypted
    value it indexes). Plain SHA-256 of a PAN/account number is brute-forceable
    and must not be used for lookup.
    """
    key = (getattr(settings, "FIELD_ENCRYPTION_KEY", "") or "").encode()
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is required for lookup hashes.")
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
