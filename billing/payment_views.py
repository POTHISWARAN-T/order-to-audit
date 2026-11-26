from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from masters.permissions import role_required

from .models import Invoice, Payment
from .receivables import ageing_report, BUCKET_LABELS, outstanding, paid_amount, record_payment


def read_payment_form(post):
    """Check what was typed. Raises ValueError with a clear message if something is wrong."""
    try:
        invoice = Invoice.objects.get(pk=post.get("invoice", ""))
    except (Invoice.DoesNotExist, ValueError):
        raise ValueError("Choose an invoice.")
    try:
        amount = Decimal(post.get("amount", "").strip())
    except InvalidOperation:
        raise ValueError("Enter the amount as a number.")
    if not amount.is_finite():
        raise ValueError("Enter the amount as a number.")
    try:
        payment_date = date.fromisoformat(post.get("payment_date", ""))
    except ValueError:
        raise ValueError("Enter a valid payment date.")
    mode = post.get("mode", "")
    if mode not in dict(Payment.MODES):
        raise ValueError("Choose a payment mode.")
    reference = post.get("reference", "").strip()[:60]
    return invoice, amount.quantize(Decimal("0.01")), payment_date, mode, reference


@role_required("Admin")
def payments_home(request):
    if request.method == "POST":
        try:
            invoice, amount, payment_date, mode, reference = read_payment_form(request.POST)
            record_payment(invoice, amount, payment_date, mode, reference, request.user)
            messages.success(
                request,
                f"Recorded Rs {amount} against {invoice.invoice_number}. "
                f"Outstanding on this invoice: Rs {outstanding(invoice)}.",
            )
        except ValueError as error:
            messages.error(request, str(error))
        return redirect("payments_home")

    invoices = (
        Invoice.objects.select_related("customer")
        .prefetch_related("payments")
        .order_by("invoice_date", "pk")
    )
    items = [
        {"invoice": i, "paid": paid_amount(i), "outstanding": outstanding(i)}
        for i in invoices
    ]
    ageing_rows, ageing_total = ageing_report()
    context = {
        "items": items,
        "open_items": [x for x in items if x["outstanding"] > 0],
        "payments": Payment.objects.select_related("invoice", "invoice__customer").order_by("-created_at"),
        "modes": Payment.MODES,
        "today": timezone.localdate().isoformat(),
        "bucket_labels": BUCKET_LABELS,
        "ageing_rows": ageing_rows,
        "ageing_total": ageing_total,
    }
    return render(request, "billing/payments_home.html", context)