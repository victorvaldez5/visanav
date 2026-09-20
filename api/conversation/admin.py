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
    """Message rows are visible for support/debugging, but their CONTENT is not.

    `parts` and `sources` are decrypted on read by EncryptedJSONField, and
    `instructions` is the agent's system prompt — none of it should be casually
    readable by a staff member browsing the admin. At-rest encryption only shrinks
    the blast radius of a storage breach; it does nothing against an insider with
    an admin login, so we simply never render the content here. Retention and
    legal-hold work operate on Conversation and need only message metadata, so we
    surface metadata and exclude the content entirely. See core/encryption.py.
    """

    list_display = ("id", "conversation", "kind", "model_name", "timestamp")
    list_filter = ("kind",)
    # Never build a form field for the decrypted content or the system prompt.
    exclude = ("parts", "instructions", "sources")
    readonly_fields = ("conversation", "kind", "model_name", "timestamp")

    def has_add_permission(self, request):
        # Messages are only ever written by the chat pipeline, never by hand
        # (and `parts` is required but excluded here, so an admin add can't work).
        return False


admin.site.register(Feedback)
