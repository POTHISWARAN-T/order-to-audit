from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    CREATED = "CREATED"
    CHANGED = "CHANGED"
    DELETED = "DELETED"
    ACTIONS = [(CREATED, "Created"), (CHANGED, "Changed"), (DELETED, "Deleted")]

    model_name = models.CharField(max_length=60)  # for example sales.Order
    object_id = models.CharField(max_length=20)
    object_repr = models.CharField(max_length=200)
    action = models.CharField(max_length=7, choices=ACTIONS)
    changes = models.TextField(blank=True)  # "field: old -> new", one part per changed field
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.get_action_display()} {self.model_name} {self.object_id}"