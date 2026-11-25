from decimal import Decimal

from django.db import transaction
from django.shortcuts import redirect, render

from masters.models import Customer, Item
from masters.permissions import role_required

from .models import Order, OrderLine


@role_required("Salesman")
def new_order(request):
    customers = Customer.objects.order_by("name")
    products = Item.objects.filter(item_type=Item.FINISHED, rate__gt=0).order_by("name")
    error = ""
    selected_customer = request.POST.get("customer", "")
    notes = request.POST.get("notes", "")

    if request.method == "POST":
        customer = (
            customers.filter(pk=selected_customer).first()
            if selected_customer.isdigit()
            else None
        )
        lines = []
        for product in products:
            raw = request.POST.get(f"qty_{product.pk}", "").strip()
            if not raw:
                continue
            if not raw.isdigit():
                error = f"Quantity for {product.name} must be a whole number."
                break
            if int(raw) > 0:
                lines.append((product, int(raw)))

        if not error and customer is None:
            error = "Please select a customer."
        elif not error and not lines:
            error = "Enter a quantity for at least one product."

        if not error:
            with transaction.atomic():
                order = Order.objects.create(
                    customer=customer, salesman=request.user, notes=notes[:200]
                )
                for product, qty in lines:
                    # The rate is copied onto the line, so later price changes
                    # never alter an order that was already placed
                    OrderLine.objects.create(
                        order=order, product=product, quantity=qty, rate=product.rate
                    )
            return redirect("my_orders")

    rows = [
        {"product": p, "qty": request.POST.get(f"qty_{p.pk}", "")} for p in products
    ]
    return render(
        request,
        "sales/new_order.html",
        {
            "customers": customers,
            "rows": rows,
            "error": error,
            "selected_customer": selected_customer,
            "notes": notes,
        },
    )


@role_required("Salesman")
def my_orders(request):
    orders = (
        Order.objects.filter(salesman=request.user)
        .select_related("customer")
        .prefetch_related("lines__product")
        .order_by("-created_at")
    )
    totals = {}
    for order in orders:
        if order.status == Order.REJECTED:
            continue
        name = order.customer.name
        totals[name] = totals.get(name, Decimal("0.00")) + order.total
    return render(
        request,
        "sales/my_orders.html",
        {"orders": orders, "customer_sales": sorted(totals.items())},
    )