from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from masters.models import Item

from .services import get_balance


@login_required
def stock_summary(request):
    rows = [
        {"item": item, "balance": get_balance(item)}
        for item in Item.objects.order_by("item_type", "name")
    ]
    return render(request, "inventory/stock_summary.html", {"rows": rows})