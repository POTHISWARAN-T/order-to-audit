from django.conf import settings
from django.db import models
from django.utils import timezone

from masters.models import Item


class StockMovement(models.Model):
    OPENING = "OPENING"
    PURCHASE = "PURCHASE"
    PRODUCTION_ISSUE = "PROD_ISSUE"
    PRODUCTION_OUTPUT = "PROD_OUTPUT"
    WASTAGE = "WASTAGE"
    DISPATCH = "DISPATCH"
    ADJUSTMENT = "ADJUST"
    TYPES = [
        (OPENING, "Opening balance"),
        (PURCHASE, "Purchase receipt"),
        (PRODUCTION_ISSUE, "Issued to production"),
        (PRODUCTION_OUTPUT, "Production output"),
        (WASTAGE, "Wastage / damage"),
        (DISPATCH, "Dispatch to customer"),
        (ADJUSTMENT, "Adjustment"),
    ]

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)  # + in, - out
    movement_type = models.CharField(max_length=12, choices=TYPES)
    source_ref = models.CharField(max_length=100, help_text="e.g. Purchase #1")
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.item} {self.quantity} ({self.movement_type})"