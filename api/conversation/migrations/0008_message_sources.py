"""Add Message.sources — official citations for an assistant reply.

Stores the retrieval results (title / source_url / last_verified / score) that
grounded a response, so the UI can render clickable source links — including on
history reload, not just during the live stream. Encrypted at rest like
Message.parts (which sources a turn cited can hint at what the user asked).
Nullable; only assistant response messages set it.
"""
import core.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("conversation", "0007_encrypt_message_parts"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="sources",
            field=core.fields.EncryptedJSONField(blank=True, null=True),
        ),
    ]
