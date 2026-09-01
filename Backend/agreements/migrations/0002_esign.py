from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agreements", "0001_initial")]

    operations = [
        migrations.AddField(model_name="agreement", name="esign_document_id", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="agreement", name="esign_request_id", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="agreement", name="esign_status", field=models.CharField(blank=True, max_length=30)),
    ]
