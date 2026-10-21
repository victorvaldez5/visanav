from django.contrib import admin

from .models import IngestRun, KnowledgeChunk


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("chunk_id", "country", "topic", "title", "updated_at")
    list_filter = ("country", "corpus", "instrument", "topic", "source_type")
    search_fields = ("chunk_id", "doc_id", "title", "text")
    # The embedding is a 1024-float vector — never useful to render/edit by hand.
    exclude = ("embedding",)
    readonly_fields = ("updated_at",)


@admin.register(IngestRun)
class IngestRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "corpus", "country", "status", "chunks", "embedded", "marker")
    list_filter = ("corpus", "status", "country")
    readonly_fields = [f.name for f in IngestRun._meta.fields]
