from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicIdSequence",
            fields=[
                ("prefix", models.CharField(max_length=12, primary_key=True, serialize=False)),
                ("current", models.PositiveBigIntegerField(default=0)),
            ],
        ),
    ]
