from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import StockMovement


def get_balance(item):
    """Closing balance = sum of every movement for this item."""
    total = StockMovement.objects.filter(item=item).aggregate(t=Sum("quantity"))["t"]
    return total or Decimal("0")


@transaction.atomic
def post_purchase(purchase):
    """Every purchase adds one plus-row to the stock ledger."""
    return StockMovement.objects.create(
        item=purchase.item,
        quantity=purchase.quantity,
        movement_type=StockMovement.PURCHASE,
        source_ref=f"Purchase #{purchase.pk}",
        created_by=purchase.created_by,
    )