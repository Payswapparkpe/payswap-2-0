"""Encrypt sensitive onboarding step fields written before encryption-at-rest."""

from django.db import migrations

from core.crypto import encrypt_text

SENSITIVE_KEYS = ("pan", "gstin", "cin", "llpin")
_FERNET_PREFIX = "gAAAA"


def encrypt_existing_steps(apps, schema_editor):
    OnboardingStep = apps.get_model("merchants", "OnboardingStep")
    for step in OnboardingStep.objects.all().iterator():
        data = step.data
        if not isinstance(data, dict):
            continue
        changed = False
        for key in SENSITIVE_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value and not value.startswith(_FERNET_PREFIX):
                data[key] = encrypt_text(value)
                changed = True
        if changed:
            step.save(update_fields=["data"])


class Migration(migrations.Migration):
    dependencies = [("merchants", "0002_remove_beneficialowner_pan_and_more")]
    # Not reversible without retaining plaintext somewhere, which defeats the
    # purpose; the forward pass is idempotent so re-applying is safe.
    operations = [migrations.RunPython(encrypt_existing_steps, migrations.RunPython.noop)]
