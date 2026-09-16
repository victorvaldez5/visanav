"""Encrypt Message.parts at rest.

Switches the column from jsonb to Fernet-encrypted text and re-writes any
existing rows through the encrypting field. The AlterField casts existing
jsonb to text (plaintext JSON), which EncryptedJSONField reads via its
plaintext fallback; the data step then re-saves each row so it is stored
encrypted.

Forward-only in practice: reversing would need to write plaintext back, but the
field always encrypts on save, so the data step's reverse is a no-op. On an
empty database (tests build from models and skip migrations; a fresh deploy has
no rows) there is nothing to convert.
"""
import core.fields
from django.db import migrations


def encrypt_existing_rows(apps, schema_editor):
    Message = apps.get_model("conversation", "Message")
    for message in Message.objects.all().iterator(chunk_size=500):
        # Reading decodes the (plaintext) value; saving writes it back encrypted.
        message.save(update_fields=["parts"])


class Migration(migrations.Migration):

    dependencies = [
        ("conversation", "0006_conversation_retention"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="parts",
            field=core.fields.EncryptedJSONField(),
        ),
        migrations.RunPython(encrypt_existing_rows, migrations.RunPython.noop),
    ]
