from django.contrib import admin

from network.models import OrganizationSubmission


@admin.register(OrganizationSubmission)
class OrganizationSubmissionAdmin(admin.ModelAdmin):
    """Review queue for NGO 'request to be included' submissions.

    Submissions arrive PENDING; approve/reject here. Approval is a human
    decision on purpose — do not wire up auto-listing."""

    list_display = (
        "organization_name",
        "intent",
        "status",
        "offers_pro_bono",
        "state",
        "contact_email",
        "created_at",
    )
    list_filter = ("status", "intent", "offers_pro_bono", "state")
    list_editable = ("status",)  # triage straight from the list
    search_fields = ("organization_name", "contact_name", "contact_email", "city", "state")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ("mark_approved", "mark_rejected")

    fieldsets = (
        ("Submission", {
            "fields": (
                "organization_name",
                ("contact_name", "contact_email", "contact_phone"),
                "website",
                ("city", "state"),
                "offers_pro_bono",
                "intent",
                "message",
            ),
        }),
        ("Review", {
            "fields": ("status", "reviewer_notes", ("created_at", "updated_at")),
        }),
    )

    @admin.action(description="Mark selected submissions as approved")
    def mark_approved(self, request, queryset):
        updated = queryset.update(status=OrganizationSubmission.Status.APPROVED)
        self.message_user(request, f"{updated} submission(s) approved.")

    @admin.action(description="Mark selected submissions as rejected")
    def mark_rejected(self, request, queryset):
        updated = queryset.update(status=OrganizationSubmission.Status.REJECTED)
        self.message_user(request, f"{updated} submission(s) rejected.")
