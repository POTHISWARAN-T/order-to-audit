from django.shortcuts import render

from masters.models import Item
from masters.permissions import STOCK_ROLES, role_required

from .services import get_balance


@role_required(*STOCK_ROLES)
def stock_summary(request):
    rows = [
        {"item": item, "balance": get_balance(item)}
        for item in Item.objects.order_by("item_type", "name")
    ]
    return render(request, "inventory/stock_summary.html", {"rows": rows})