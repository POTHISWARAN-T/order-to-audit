from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from masters.models import Item


class ProductionRun(models.Model):
    product = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        limit_choices_to={"item_type": "FG", "bom__isnull": False},
    )
    batches = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("1"))
    good_output = models.PositiveIntegerField(help_text="Good packets produced")
    run_date = models.DateField(default=timezone.localdate)
    notes = models.CharField(max_length=200, blank=True)

    # Filled in automatically when the run is posted
    expected_output = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )
    yield_variance_pct = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    posted = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Run #{self.pk}: {self.product}"


class ProductionRunLine(models.Model):
    run = models.ForeignKey(ProductionRun, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        limit_choices_to={"item_type__in": ["RAW", "PACK"]},
    )
    actual_qty = models.DecimalField(
        max_digits=12, decimal_places=3, help_text="Used in good output"
    )
    wasted_qty = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal("0"), help_text="Damaged or scrap"
    )

    # Filled in automatically when the run is posted
    planned_qty = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    variance_pct = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    flagged = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.item} in run #{self.run_id}"
    
class RunOverhead(models.Model):
    LABOUR = "LABOUR"
    GAS = "GAS"
    POWER = "POWER"
    OTHER = "OTHER"
    KINDS = [(LABOUR, "Labour"), (GAS, "Gas"), (POWER, "Power"), (OTHER, "Other")]

    run = models.ForeignKey(ProductionRun, on_delete=models.PROTECT, related_name="overheads")
    kind = models.CharField(max_length=8, choices=KINDS)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="A negative amount corrects an earlier entry",
    )
    note = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.get_kind_display()} Rs {self.amount} on run #{self.run_id}"    
    
