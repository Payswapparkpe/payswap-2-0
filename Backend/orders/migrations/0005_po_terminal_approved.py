# Generated manually for deep-clean: PO lifecycle ends at APPROVED.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0004_alter_orderevent_from_status")]

    operations = [
        migrations.AlterField(
            model_name="paymentorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("SUBMITTED", "Submitted"),
                    ("UNDER_REVIEW", "Under review"),
                    ("CHANGES_REQUESTED", "Changes requested"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="DRAFT",
                max_length=30,
            ),
        ),
    ]
