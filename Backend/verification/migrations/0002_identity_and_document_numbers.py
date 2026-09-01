from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("verification", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="document_number_encrypted",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="document",
            name="document_last4",
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name="document",
            name="provider_ref",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="document",
            name="file",
            field=models.FileField(blank=True, upload_to="documents/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="bankaccount",
            name="provider_ref",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.CreateModel(
            name="IdentityCheck",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=20)),
                ("document_last4", models.CharField(blank=True, max_length=4)),
                ("provider", models.CharField(default="cashfree", max_length=20)),
                ("provider_ref", models.CharField(blank=True, max_length=64)),
                ("status", models.CharField(max_length=20)),
                ("name_at_source", models.CharField(blank=True, max_length=150)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identity_checks",
                        to="merchants.merchant",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
