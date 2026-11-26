from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "model_name", "object_id", "object_repr")
    list_filter = ("action", "model_name", "user")
    search_fields = ("object_repr", "changes")

    # The log is a record. Nobody adds, edits or deletes entries.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False