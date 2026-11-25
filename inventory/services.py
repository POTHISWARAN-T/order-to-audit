from decimal import Decimal

from django.db.models import Sum

from .models import StockMovement


def get_balance(item):
    """Closing balance = sum of every movement for this item."""
    total = StockMovement.objects.filter(item=item).aggregate(t=Sum("quantity"))["t"]
    return total or Decimal("0")