from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from inventory.models import StockMovement
from sales.models import Order

from .models import CreditNote
from .services import financial_year


@transaction.atomic
def issue_credit_note(invoice, reason, goods_returned, user):
    """Cancel an invoice in full. The invoice stays on record, the credit note reverses it."""
    reason = reason.strip()
    if not reason:
        raise ValueError("Give a reason for the credit note.")
    if CreditNote.objects.filter(invoice=invoice).exists():
        raise ValueError("This invoice already has a credit note.")
    if goods_returned and invoice.dispatched_at is None:
        raise ValueError("Goods can be returned only after they were dispatched.")

    today = timezone.localdate()
    fin_year = financial_year(today)
    last = CreditNote.objects.filter(fin_year=fin_year).aggregate(m=Max("sequence"))["m"]
    sequence = (last or 0) + 1
    note = CreditNote.objects.create(
        invoice=invoice,
        fin_year=fin_year,
        sequence=sequence,
        credit_note_number=f"CN/{fin_year}/{sequence:04d}",
        note_date=today,
        reason=reason[:200],
        goods_returned=goods_returned,
        taxable_value=invoice.taxable_value,
        cgst=invoice.cgst,
        sgst=invoice.sgst,
        igst=invoice.igst,
        total_amount=invoice.total_amount,
        created_by=user,
    )

    if goods_returned:
        for line in invoice.lines.select_related("product"):
            StockMovement.objects.create(
                item=line.product,
                quantity=Decimal(line.quantity),
                movement_type=StockMovement.ADJUSTMENT,
                source_ref=note.credit_note_number,
                note="Goods returned by the customer",
                created_by=user,
            )

    order = invoice.order
    order.status = Order.CANCELLED
    order.save(update_fields=["status"])
    return note