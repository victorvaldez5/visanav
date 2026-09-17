from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_alter_profile_preferred_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="retain_history",
            field=models.BooleanField(default=False),
        ),
    ]
