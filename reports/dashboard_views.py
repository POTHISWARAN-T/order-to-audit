from collections import Counter
from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from billing.models import CreditNote, Invoice, Payment
from billing.receivables import ageing_report
from inventory.services import get_balance
from masters.models import Item
from masters.permissions import role_required
from production.costing import product_summary, run_cost
from production.models import ProductionRun
from production.services import VARIANCE_TOLERANCE, is_flagged
from sales.models import Order
from sales.services import available_stock

from .builders import bounds

ZERO = Decimal("0.00")


def plain(value):
    """200.000 becomes '200' and 10.500 becomes '10.5'."""
    return format(value.normalize(), "f")


def total_of(queryset, field):
    return queryset.aggregate(t=Sum(field))["t"] or ZERO


def todays_orders(today):
    first, after = bounds(today, today)
    orders = list(
        Order.objects.filter(created_at__gte=first, created_at__lt=after)
        .select_related("customer", "salesman")
        .prefetch_related("lines")
        .order_by("-created_at")
    )
    live = [o for o in orders if o.status not in (Order.REJECTED, Order.CANCELLED)]
    return {
        "orders": orders,
        "count": len(orders),
        "value": sum((o.total for o in live), ZERO),
        "by_status": dict(Counter(o.get_status_display() for o in orders)),
    }


def stock_levels():
    rows = []
    for item in Item.objects.order_by("item_type", "name"):
        free = available_stock(item) if item.item_type == Item.FINISHED else None
        rows.append({"item": item, "balance": get_balance(item), "free": free})
    return rows


def variance_alerts(limit=10):
    """Yield and material variances beyond the tolerance in the latest production runs."""
    alerts = []
    runs = (
        ProductionRun.objects.select_related("product")
        .prefetch_related("lines__item")
        .order_by("-run_date", "-pk")[:limit]
    )
    for run in runs:
        variance = run.yield_variance_pct
        if run.posted and variance is not None and is_flagged(variance):
            alerts.append({
                "run": run,
                "what": "Yield",
                "detail": f"{run.good_output} good packets against {plain(run.expected_output)} expected",
                "variance_text": f"{variance:+.2f}",
            })
        for line in run.lines.all():
            if not line.flagged:
                continue
            if line.variance_pct is None:
                alerts.append({
                    "run": run,
                    "what": line.item.name,
                    "detail": "used, but not part of the recipe",
                    "variance_text": "n/a",
                })
                continue
            used = line.actual_qty + line.wasted_qty
            alerts.append({
                "run": run,
                "what": line.item.name,
                "detail": f"{plain(used)} {line.item.unit} used against {plain(line.planned_qty)} planned",
                "variance_text": f"{line.variance_pct:+.2f}",
            })
    return alerts


def cost_summary():
    runs = ProductionRun.objects.select_related("product").prefetch_related(
        "lines__item", "overheads"
    )
    return product_summary([run_cost(run) for run in runs])


def dues():
    rows, grand = ageing_report()
    top = sorted(rows, key=lambda r: r["total"], reverse=True)[:5]
    return {
        "total": grand["total"],
        "overdue": sum(grand["buckets"][1:], ZERO),
        "top": top,
    }


@role_required("Owner", "Admin", "Accountant")
def dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    month_sales = total_of(
        Invoice.objects.filter(invoice_date__range=(month_start, today)), "taxable_value"
    )
    month_credits = total_of(
        CreditNote.objects.filter(note_date__range=(month_start, today)), "taxable_value"
    )
    context = {
        "today": today,
        "month_sales": month_sales,
        "month_credits": month_credits,
        "net_sales": month_sales - month_credits,
        "collected": total_of(
            Payment.objects.filter(payment_date__range=(month_start, today)), "amount"
        ),
        "orders_today": todays_orders(today),
        "waiting": Order.objects.filter(status=Order.SUBMITTED).count(),
        "stock_rows": stock_levels(),
        "alerts": variance_alerts(),
        "tolerance": VARIANCE_TOLERANCE,
        "summary": cost_summary(),
        "dues": dues(),
    }
    return render(request, "reports/dashboard.html", context)