# Generated manually for deep-clean: WebhookEvent moved from payments to audit.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("audit", "0004_apicalllog")]

    operations = [
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=20)),
                ("event_id", models.CharField(max_length=80)),
                ("event_type", models.CharField(blank=True, max_length=80)),
                ("signature_valid", models.BooleanField(default=False)),
                ("payload", models.JSONField(default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("processing_result", models.CharField(default="received", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="webhookevent",
            constraint=models.UniqueConstraint(fields=["provider", "event_id"], name="unique_provider_event"),
        ),
    ]
