import json

from django.contrib.auth import get_user_model

from core.crypto import decrypt_text, encrypt_text

SECURE_CONTEXT_KEY = "__secure__"


def serialize_context(context: dict | None) -> dict:
    payload = dict(context or {})
    user = payload.pop("user", None)
    if user is not None:
        payload["user_id"] = getattr(user, "pk", user)
    return payload


def protect_context(context: dict | None) -> dict:
    """Encrypt a serialized context so secrets (e.g. OTP codes) never sit in
    the Celery broker or task args in plaintext."""
    serialized = serialize_context(context)
    return {SECURE_CONTEXT_KEY: encrypt_text(json.dumps(serialized))}


def hydrate_context(payload: dict) -> dict:
    data = dict(payload or {})
    if SECURE_CONTEXT_KEY in data:
        decrypted = decrypt_text(data.pop(SECURE_CONTEXT_KEY))
        data = json.loads(decrypted) if decrypted else {}
    user_id = data.pop("user_id", None)
    if user_id:
        User = get_user_model()
        data["user"] = User.objects.filter(pk=user_id).first()
    return data
