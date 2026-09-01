"""Cashfree Secure ID 2FA signature (x-cf-signature).

When the server IP is not whitelisted, encrypt ``{client_id}.{unix_epoch}`` with
the public key downloaded from the Cashfree dashboard (RSA OAEP SHA-1).
"""

from __future__ import annotations

import base64
import logging
import time
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 480  # refresh before Cashfree's ~10 minute expiry
_cached: tuple[int, str] | None = None


@lru_cache(maxsize=4)
def _load_public_key(pem_path: str):
    data = Path(pem_path).read_bytes()
    return serialization.load_pem_public_key(data)


def generate_cf_signature(*, client_id: str, public_key_path: str) -> str:
    global _cached
    now = int(time.time())
    if _cached and now - _cached[0] < _CACHE_TTL_SECONDS:
        return _cached[1]
    if not client_id or not public_key_path:
        return ""
    try:
        public_key = _load_public_key(public_key_path)
        payload = f"{client_id}.{now}".encode()
        encrypted = public_key.encrypt(
            payload,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None,
            ),
        )
        signature = base64.b64encode(encrypted).decode("ascii")
        _cached = (now, signature)
        return signature
    except OSError:
        logger.warning("cashfree public key not readable at %s", public_key_path)
        return ""
    except Exception:
        logger.exception("failed to generate cashfree x-cf-signature")
        return ""
