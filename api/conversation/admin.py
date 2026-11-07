from django.contrib import admin

from .models import Conversation, Feedback, FeedbackDaily, Message, UsageDaily


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


class ReadOnlyAdmin(admin.ModelAdmin):
    """Aggregate counters are written only by the app, never by hand."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UsageDaily)
class UsageDailyAdmin(ReadOnlyAdmin):
    list_display = ("date", "locale", "turns", "new_conversations", "turns_searched",
                    "turns_with_sources", "turns_with_resources", "failed_turns")
    ordering = ("-date", "locale")


@admin.register(FeedbackDaily)
class FeedbackDailyAdmin(ReadOnlyAdmin):
    list_display = ("date", "helpful", "not_helpful")
    ordering = ("-date",)
