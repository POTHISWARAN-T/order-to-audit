from decimal import Decimal

from django.db.models import Sum

from inventory.services import get_balance

from .models import Order, OrderLine

# Orders that have been promised stock but have not been dispatched yet
RESERVING = (Order.APPROVED, Order.INVOICED)


def available_stock(product, exclude_order=None):
    """Finished goods in the ledger minus what other approved orders already claim."""
    claimed = OrderLine.objects.filter(product=product, order__status__in=RESERVING)
    if exclude_order is not None:
        claimed = claimed.exclude(order=exclude_order)
    total = claimed.aggregate(t=Sum("quantity"))["t"] or 0
    return get_balance(product) - Decimal(total)


def stock_rows(order):
    """One row per order line: free stock and shortage."""
    rows = []
    for line in order.lines.select_related("product"):
        available = available_stock(line.product, exclude_order=order)
        shortage = max(Decimal("0"), Decimal(line.quantity) - available)
        rows.append({"line": line, "available": available, "shortage": shortage})
    return rows