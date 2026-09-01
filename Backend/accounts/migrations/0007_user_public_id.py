from django.db import migrations, models

from accounts.user_ids import assign_public_id


def backfill_user_public_ids(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.order_by("date_joined", "id"):
        if user.public_id:
            continue
        assign_public_id(user)
        user.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_securitycredential_recoverycode"),
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="public_id",
            field=models.CharField(db_index=True, max_length=20, null=True, unique=True),
        ),
        migrations.RunPython(backfill_user_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="public_id",
            field=models.CharField(db_index=True, max_length=20, unique=True),
        ),
    ]
