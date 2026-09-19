import pgvector.django
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # CREATE EXTENSION IF NOT EXISTS vector — must precede the vector column.
        # (Skipped under pytest --no-migrations; see api/conftest.py.)
        pgvector.django.VectorExtension(),
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_id", models.CharField(max_length=128, unique=True)),
                ("doc_id", models.CharField(max_length=255)),
                ("country", models.CharField(db_index=True, max_length=8)),
                ("text", models.TextField()),
                ("embedding", pgvector.django.VectorField(dimensions=1024)),
                ("authority", models.CharField(blank=True, max_length=255, null=True)),
                ("topic", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ("title", models.CharField(blank=True, max_length=512, null=True)),
                ("lang", models.CharField(blank=True, max_length=16, null=True)),
                ("source_url", models.URLField(blank=True, max_length=1024, null=True)),
                ("source_type", models.CharField(blank=True, max_length=64, null=True)),
                ("last_verified", models.DateField(blank=True, null=True)),
                ("forms", models.JSONField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="knowledgechunk",
            index=pgvector.django.HnswIndex(
                name="knowledge_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
