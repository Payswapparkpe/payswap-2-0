from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdmin):
    list_display = ["created_at", "action", "actor", "resource_type", "resource_id", "result"]
    list_filter = ["action", "result", "resource_type"]
    search_fields = ["action", "resource_id", "request_id", "reason"]
    readonly_fields = [
        "actor",
        "action",
        "resource_type",
        "resource_id",
        "result",
        "reason",
        "before",
        "after",
        "ip_address",
        "request_id",
        "user_agent",
        "created_at",
    ]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
