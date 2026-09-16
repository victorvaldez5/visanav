from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conversation", "0005_remove_uuid_null_conversation"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="conversation",
            name="legal_hold",
            field=models.BooleanField(default=False),
        ),
    ]
