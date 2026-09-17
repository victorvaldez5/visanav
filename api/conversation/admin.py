from django.contrib import admin

from .models import Conversation, Message, Feedback


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "uuid", "user", "created_at", "expires_at", "legal_hold")
    list_filter = ("legal_hold",)
    list_editable = ("legal_hold",)
    search_fields = ("uuid", "user__username", "user__email")
    readonly_fields = ("uuid", "created_at")
    actions = ("place_legal_hold", "lift_legal_hold")

    @admin.action(description="Place legal hold (exempt from auto-deletion)")
    def place_legal_hold(self, request, queryset):
        updated = queryset.update(legal_hold=True)
        self.message_user(request, f"Placed a legal hold on {updated} conversation(s).")

    @admin.action(description="Lift legal hold")
    def lift_legal_hold(self, request, queryset):
        updated = queryset.update(legal_hold=False)
        self.message_user(request, f"Lifted the legal hold on {updated} conversation(s).")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "kind", "model_name", "timestamp")
    list_filter = ("kind",)
    # `parts` is encrypted at rest and decoded to native JSON on read; keep the
    # whole row read-only so the admin never round-trips it through a form.
    readonly_fields = ("conversation", "parts", "instructions", "kind", "model_name", "timestamp")


admin.site.register(Feedback)
