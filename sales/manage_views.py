from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from masters.permissions import role_required

from .models import Order
from .services import stock_rows


def parse_edits(request, order):
    """Read the quantity and rate typed for each line. Returns (values, errors)."""
    values, errors = {}, []
    for line in order.lines.select_related("product"):
        name = line.product.name
        raw_qty = request.POST.get(f"qty_{line.pk}", "").strip()
        raw_rate = request.POST.get(f"rate_{line.pk}", "").strip()
        if not raw_qty.isdigit():
            errors.append(f"Quantity for {name} must be a whole number.")
            continue
        try:
            rate = Decimal(raw_rate)
        except InvalidOperation:
            errors.append(f"Rate for {name} must be a number.")
            continue
        if not rate.is_finite() or rate < 0:
            errors.append(f"Rate for {name} must be zero or more.")
            continue
        values[line.pk] = (int(raw_qty), rate.quantize(Decimal("0.01")))
    return values, errors


@role_required("Admin")
def order_list(request):
    orders = (
        Order.objects.select_related("customer", "salesman")
        .prefetch_related("lines__product")
        .order_by("-created_at")
    )
    return render(request, "sales/order_list.html", {"orders": orders})


@role_required("Admin")
def order_review(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer", "salesman"), pk=pk
    )
    editable = order.status == Order.SUBMITTED
    errors = []
    keep_posted = False

    if request.method == "POST" and editable:
        action = request.POST.get("action")

        if action == "reject":
            order.status = Order.REJECTED
            order.save(update_fields=["status"])
            return redirect("order_list")

        values, errors = parse_edits(request, order)
        if not errors and all(qty == 0 for qty, _ in values.values()):
            errors.append("Every quantity is zero. Use Reject instead.")

        if errors:
            keep_posted = True
        else:
            with transaction.atomic():
                for line in order.lines.all():
                    qty, rate = values[line.pk]
                    if qty == 0:
                        line.delete()
                    else:
                        line.quantity = qty
                        line.rate = rate
                        line.save()

            if action == "approve":
                if any(row["shortage"] > 0 for row in stock_rows(order)):
                    errors.append(
                        "Cannot approve: stock does not cover this order. "
                        "Reduce the quantity or reject it."
                    )
                else:
                    order.status = Order.APPROVED
                    order.save(update_fields=["status"])
                    return redirect("order_list")

    rows = stock_rows(order)
    for row in rows:
        line = row["line"]
        if keep_posted:
            row["qty"] = request.POST.get(f"qty_{line.pk}", line.quantity)
            row["rate"] = request.POST.get(f"rate_{line.pk}", line.rate)
        else:
            row["qty"] = line.quantity
            row["rate"] = line.rate

    return render(
        request,
        "sales/order_review.html",
        {
            "order": order,
            "rows": rows,
            "editable": editable,
            "errors": errors,
            "has_shortage": any(row["shortage"] > 0 for row in rows),
        },
    )