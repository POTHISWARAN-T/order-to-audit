from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from masters.permissions import role_required

from .costing import product_summary, run_cost
from .models import ProductionRun, RunOverhead


def read_overhead_form(post):
    """Check what was typed. Raises ValueError with a clear message if something is wrong."""
    try:
        run = ProductionRun.objects.get(pk=post.get("run", ""))
    except (ProductionRun.DoesNotExist, ValueError):
        raise ValueError("Choose a production run.")
    kind = post.get("kind", "")
    if kind not in dict(RunOverhead.KINDS):
        raise ValueError("Choose the type of cost.")
    try:
        amount = Decimal(post.get("amount", "").strip())
    except InvalidOperation:
        raise ValueError("Enter the amount as a number.")
    if not amount.is_finite() or amount == 0:
        raise ValueError("Enter an amount other than zero.")
    return run, kind, amount.quantize(Decimal("0.01")), post.get("note", "").strip()[:100]


@role_required("Admin", "Production", "Accountant", "Owner")
def costing_home(request):
    user = request.user
    can_edit = user.is_superuser or user.groups.filter(name__in=("Admin", "Production")).exists()

    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        try:
            run, kind, amount, note = read_overhead_form(request.POST)
        except ValueError as error:
            messages.error(request, str(error))
        else:
            RunOverhead.objects.create(
                run=run, kind=kind, amount=amount, note=note, created_by=user
            )
            messages.success(request, f"Saved Rs {amount} against run #{run.pk}.")
        return redirect("costing_home")

    runs = (
        ProductionRun.objects.select_related("product")
        .prefetch_related("lines__item", "overheads")
        .order_by("-run_date", "-pk")
    )
    costs = [run_cost(run) for run in runs]
    context = {
        "costs": costs,
        "summary": product_summary(costs),
        "kinds": RunOverhead.KINDS,
        "can_edit": can_edit,
    }
    return render(request, "production/costing_home.html", context)