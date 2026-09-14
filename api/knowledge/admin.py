from django.contrib import admin

from .models import KnowledgeChunk


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("chunk_id", "country", "topic", "title", "updated_at")
    list_filter = ("country", "topic", "source_type")
    search_fields = ("chunk_id", "doc_id", "title", "text")
    # The embedding is a 1024-float vector — never useful to render/edit by hand.
    exclude = ("embedding",)
    readonly_fields = ("updated_at",)
