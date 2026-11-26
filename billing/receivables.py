from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Invoice, Payment

ZERO = Decimal("0.00")
BUCKET_LABELS = ["0-30 days", "31-60 days", "61-90 days", "Over 90 days"]


def paid_amount(invoice):
    """Total of all payments received against this invoice."""
    return sum((p.amount for p in invoice.payments.all()), ZERO)


def outstanding(invoice):
    """What the customer still owes: invoice total minus payments."""
    return invoice.total_amount - paid_amount(invoice)


@transaction.atomic
def record_payment(invoice, amount, payment_date, mode, reference, user):
    if amount <= 0:
        raise ValueError("The amount must be more than zero.")
    due = outstanding(invoice)
    if amount > due:
        raise ValueError(f"The amount is more than the Rs {due} outstanding on this invoice.")
    return Payment.objects.create(
        invoice=invoice,
        amount=amount,
        payment_date=payment_date,
        mode=mode,
        reference=reference,
        received_by=user,
    )


def bucket_index(age_days):
    if age_days <= 30:
        return 0
    if age_days <= 60:
        return 1
    if age_days <= 90:
        return 2
    return 3


def ageing_report(today=None):
    """Outstanding amount per customer, split by how old the invoice is."""
    today = today or timezone.localdate()
    rows = {}
    grand = {"buckets": [ZERO, ZERO, ZERO, ZERO], "total": ZERO}
    invoices = Invoice.objects.select_related("customer").prefetch_related("payments")
    for invoice in invoices:
        due = outstanding(invoice)
        if due <= 0:
            continue
        row = rows.setdefault(
            invoice.customer_id,
            {"customer": invoice.customer, "buckets": [ZERO, ZERO, ZERO, ZERO], "total": ZERO},
        )
        index = bucket_index((today - invoice.invoice_date).days)
        row["buckets"][index] += due
        row["total"] += due
        grand["buckets"][index] += due
        grand["total"] += due
    return sorted(rows.values(), key=lambda r: r["customer"].name), grand