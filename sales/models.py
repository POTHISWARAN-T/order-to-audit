from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from masters.models import Customer, Item


class Order(models.Model):
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVOICED = "INVOICED"
    DISPATCHED = "DISPATCHED"
    CANCELLED = "CANCELLED"
    STATUSES = [
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (INVOICED, "Invoiced"),
        (DISPATCHED, "Dispatched"),
        (CANCELLED, "Cancelled"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    salesman = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=10, choices=STATUSES, default=SUBMITTED)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def total(self):
        """Order value before tax."""
        return sum((line.amount for line in self.lines.all()), Decimal("0.00"))

    def __str__(self):
        return f"ORD-{self.pk}"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(
        Item, on_delete=models.PROTECT, limit_choices_to={"item_type": "FG"}
    )
    quantity = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=10, decimal_places=2)  # price when ordered

    @property
    def amount(self):
        return (self.quantity * self.rate).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.product} x {self.quantity}"