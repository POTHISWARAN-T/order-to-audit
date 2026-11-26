from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from inventory.models import StockMovement
from inventory.services import get_balance
from sales.models import Order

from .models import Invoice, InvoiceLine

PAISA = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value):
    """Round to 2 decimal places (paise), half up."""
    return value.quantize(PAISA, rounding=ROUND_HALF_UP)


def financial_year(day):
    """The Indian financial year runs April to March, for example 2026-27."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def is_interstate(customer):
    """Supply to another state is charged IGST, supply inside the state CGST + SGST."""
    return customer.state.strip().lower() != settings.COMPANY_STATE.strip().lower()


def line_tax(taxable, gst_rate, interstate):
    """Return (cgst, sgst, igst) for one invoice line."""
    if interstate:
        return ZERO, ZERO, money(taxable * gst_rate / 100)
    half = money(taxable * gst_rate / 200)
    return half, half, ZERO


@transaction.atomic
def create_invoice(order, user):
    """Turn an approved order into a GST tax invoice."""
    if order.status != Order.APPROVED:
        raise ValueError("Only an approved order can be invoiced.")

    today = timezone.localdate()
    fin_year = financial_year(today)
    last = Invoice.objects.filter(fin_year=fin_year).aggregate(m=Max("sequence"))["m"]
    sequence = (last or 0) + 1
    interstate = is_interstate(order.customer)

    invoice = Invoice.objects.create(
        order=order,
        fin_year=fin_year,
        sequence=sequence,
        invoice_number=f"INV/{fin_year}/{sequence:04d}",
        invoice_date=today,
        customer=order.customer,
        customer_gstin=order.customer.gstin,
        place_of_supply=order.customer.state,
        is_interstate=interstate,
        created_by=user,
    )

    taxable_sum = cgst_sum = sgst_sum = igst_sum = ZERO
    for line in order.lines.select_related("product"):
        taxable = money(Decimal(line.quantity) * line.rate)
        gst_rate = line.product.gst_rate
        cgst, sgst, igst = line_tax(taxable, gst_rate, interstate)
        InvoiceLine.objects.create(
            invoice=invoice,
            product=line.product,
            description=line.product.name,
            hsn_code=line.product.hsn_code,
            quantity=line.quantity,
            rate=line.rate,
            gst_rate=gst_rate,
            taxable_value=taxable,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
        )
        taxable_sum += taxable
        cgst_sum += cgst
        sgst_sum += sgst
        igst_sum += igst

    invoice.taxable_value = taxable_sum
    invoice.cgst = cgst_sum
    invoice.sgst = sgst_sum
    invoice.igst = igst_sum
    invoice.total_amount = taxable_sum + cgst_sum + sgst_sum + igst_sum
    invoice.save()

    order.status = Order.INVOICED
    order.save(update_fields=["status"])
    return invoice


@transaction.atomic
def dispatch_invoice(invoice, user):
    """Goods leave the factory: finished-goods stock goes down in the ledger."""
    if invoice.dispatched_at is not None:
        raise ValueError("This invoice has already been dispatched.")

    lines = list(invoice.lines.select_related("product"))
    for line in lines:
        balance = get_balance(line.product)
        if balance < line.quantity:
            raise ValueError(
                f"Not enough {line.product.name} to dispatch. "
                f"In stock: {balance}, needed: {line.quantity}."
            )

    for line in lines:
        StockMovement.objects.create(
            item=line.product,
            quantity=-Decimal(line.quantity),
            movement_type=StockMovement.DISPATCH,
            source_ref=invoice.invoice_number,
            created_by=user,
        )

    invoice.dispatched_at = timezone.now()
    invoice.dispatched_by = user
    invoice.save()

    order = invoice.order
    order.status = Order.DISPATCHED
    order.save(update_fields=["status"])