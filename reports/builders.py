from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from billing.models import Invoice, InvoiceLine, Payment
from billing.receivables import BUCKET_LABELS, ageing_report
from inventory.models import Purchase, StockMovement
from masters.models import Item
from production.models import ProductionRun
from production.services import VARIANCE_TOLERANCE

ZERO = Decimal("0.00")


def day(value):
    return value.strftime("%d-%m-%Y")


def moment(value):
    return timezone.localtime(value).strftime("%d-%m-%Y %H:%M")


def bounds(start, end):
    """The period as two aware datetimes. The end day is included."""
    tz = timezone.get_current_timezone()
    first = timezone.make_aware(datetime.combine(start, time.min), tz)
    after = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz)
    return first, after


def column_total(rows, index):
    return sum((row[index] for row in rows), ZERO)


def total_row(width, label, rows, columns):
    row = [""] * width
    row[0] = label
    for index in columns:
        row[index] = column_total(rows, index)
    return row


def sales_register(start, end):
    invoices = (
        Invoice.objects.filter(invoice_date__range=(start, end))
        .select_related("customer")
        .order_by("invoice_date", "fin_year", "sequence")
    )
    headers = [
        "Invoice no", "Date", "Customer", "Customer GSTIN", "Place of supply",
        "Taxable value", "CGST", "SGST", "IGST", "Invoice total", "Dispatched",
    ]
    rows = [
        [
            i.invoice_number, day(i.invoice_date), i.customer.name,
            i.customer_gstin or "Unregistered", i.place_of_supply,
            i.taxable_value, i.cgst, i.sgst, i.igst, i.total_amount,
            "Yes" if i.dispatched_at else "No",
        ]
        for i in invoices
    ]
    return {
        "headers": headers,
        "rows": rows,
        "totals": total_row(len(headers), "Total", rows, [5, 6, 7, 8, 9]),
    }


def sales_by_customer(start, end):
    invoices = Invoice.objects.filter(invoice_date__range=(start, end)).select_related("customer")
    grouped = {}
    for i in invoices:
        row = grouped.setdefault(i.customer_id, [i.customer.name, 0, ZERO, ZERO, ZERO])
        row[1] += 1
        row[2] += i.taxable_value
        row[3] += i.gst_total
        row[4] += i.total_amount
    rows = sorted(grouped.values(), key=lambda r: r[0])
    headers = ["Customer", "Invoices", "Taxable value", "GST", "Invoice total"]
    return {
        "headers": headers,
        "rows": rows,
        "totals": total_row(len(headers), "Total", rows, [1, 2, 3, 4]),
    }


def sales_by_product(start, end):
    lines = InvoiceLine.objects.filter(
        invoice__invoice_date__range=(start, end)
    ).select_related("product")
    grouped = {}
    for line in lines:
        row = grouped.setdefault(
            line.product_id, [line.description, line.product.unit, 0, ZERO, ZERO, ZERO]
        )
        row[2] += line.quantity
        row[3] += line.taxable_value
        row[4] += line.cgst + line.sgst + line.igst
        row[5] += line.line_total
    rows = sorted(grouped.values(), key=lambda r: r[0])
    headers = ["Product", "Unit", "Quantity", "Taxable value", "GST", "Total"]
    return {
        "headers": headers,
        "rows": rows,
        "totals": total_row(len(headers), "Total", rows, [2, 3, 4, 5]),
    }


def gst_summary(start, end):
    """Outward supplies by supply type and GST rate (GSTR-3B 3.1 / GSTR-1 shape)."""
    lines = InvoiceLine.objects.filter(
        invoice__invoice_date__range=(start, end)
    ).select_related("invoice")
    grouped = {}
    for line in lines:
        interstate = line.invoice.is_interstate
        label = "Inter-state (IGST)" if interstate else "Intra-state (CGST + SGST)"
        row = grouped.setdefault((label, line.gst_rate), [label, line.gst_rate, ZERO, ZERO, ZERO, ZERO])
        row[2] += line.taxable_value
        row[3] += line.igst
        row[4] += line.cgst
        row[5] += line.sgst
    rows = []
    for row in sorted(grouped.values(), key=lambda r: (r[0], r[1])):
        tax = row[3] + row[4] + row[5]
        rows.append(row + [tax, row[2] + tax])
    headers = [
        "Supply type", "GST rate %", "Taxable value", "IGST", "CGST", "SGST",
        "Total tax", "Invoice value",
    ]
    return {
        "headers": headers,
        "rows": rows,
        "totals": total_row(len(headers), "Total", rows, [2, 3, 4, 5, 6, 7]),
    }


def hsn_summary(start, end):
    """HSN-wise summary of outward supplies (GSTR-1 table 12 shape)."""
    lines = InvoiceLine.objects.filter(
        invoice__invoice_date__range=(start, end)
    ).select_related("product")
    grouped = {}
    for line in lines:
        key = (line.hsn_code, line.description, line.product.unit)
        row = grouped.setdefault(key, [line.hsn_code, line.description, line.product.unit, 0, ZERO, ZERO, ZERO, ZERO])
        row[3] += line.quantity
        row[4] += line.taxable_value
        row[5] += line.igst
        row[6] += line.cgst
        row[7] += line.sgst
    rows = []
    for row in sorted(grouped.values(), key=lambda r: (r[0], r[1])):
        rows.append(row + [row[4] + row[5] + row[6] + row[7]])
    headers = [
        "HSN", "Description", "UQC", "Total quantity", "Taxable value",
        "IGST", "CGST", "SGST", "Total value",
    ]
    return {
        "headers": headers,
        "rows": rows,
        "totals": total_row(len(headers), "Total", rows, [4, 5, 6, 7, 8]),
    }


def purchase_register(start, end):
    purchases = (
        Purchase.objects.filter(purchase_date__range=(start, end))
        .select_related("supplier", "item")
        .order_by("purchase_date", "pk")
    )
    headers = [
        "Purchase no", "Date", "Supplier", "Supplier GSTIN", "Bill number",
        "Item", "Unit", "Quantity", "Rate", "Amount",
    ]
    rows = [
        [
            f"P-{p.pk}", day(p.purchase_date), p.supplier.name,
            p.supplier.gstin or "Unregistered", p.bill_number,
            p.item.name, p.item.unit, p.quantity, p.rate, p.amount,
        ]
        for p in purchases
    ]
    return {
        "headers": headers,
        "rows": rows,
        "totals": total_row(len(headers), "Total", rows, [9]),
    }


def stock_summary(start, end):
    """Opening + receipts - issues = closing, for every item."""
    first, after = bounds(start, end)
    headers = ["Item", "Type", "Unit", "Opening", "Receipts (+)", "Issues and sales (-)", "Closing"]
    rows = []
    for item in Item.objects.order_by("item_type", "name"):
        movements = StockMovement.objects.filter(item=item)
        # Opening-balance entries always count as opening, whatever date they were loaded
        opening = movements.filter(
            Q(created_at__lt=first) | Q(movement_type=StockMovement.OPENING, created_at__lt=after)
        ).aggregate(t=Sum("quantity"))["t"] or ZERO
        in_period = movements.filter(created_at__gte=first, created_at__lt=after)
        receipts = in_period.filter(quantity__gt=0).exclude(
            movement_type=StockMovement.OPENING
        ).aggregate(t=Sum("quantity"))["t"] or ZERO
        issues = -(in_period.filter(quantity__lt=0).aggregate(t=Sum("quantity"))["t"] or ZERO)
        rows.append([
            item.name, item.get_item_type_display(), item.unit,
            opening, receipts, issues, opening + receipts - issues,
        ])
    return {"headers": headers, "rows": rows, "totals": None}


def stock_ledger(start, end):
    """Every stock movement in the period, with its source document."""
    first, after = bounds(start, end)
    movements = (
        StockMovement.objects.filter(created_at__gte=first, created_at__lt=after)
        .select_related("item", "created_by")
        .order_by("created_at", "pk")
    )
    balances = {}
    rows = []
    for m in movements:
        if m.item_id not in balances:
            before = StockMovement.objects.filter(
                item=m.item, created_at__lt=first
            ).aggregate(t=Sum("quantity"))["t"]
            balances[m.item_id] = before or ZERO
        balances[m.item_id] += m.quantity
        rows.append([
            moment(m.created_at), m.item.name, m.item.get_item_type_display(),
            m.get_movement_type_display(),
            m.quantity if m.quantity > 0 else "",
            -m.quantity if m.quantity < 0 else "",
            m.source_ref,
            m.created_by.username if m.created_by else "",
            balances[m.item_id],
        ])
    headers = [
        "Date and time", "Item", "Item type", "Movement", "Quantity in",
        "Quantity out", "Source document", "Entered by", "Balance after",
    ]
    return {"headers": headers, "rows": rows, "totals": None}


def production_report(start, end):
    """Planned against actual consumption, with yield and wastage, per run."""
    runs = (
        ProductionRun.objects.filter(run_date__range=(start, end))
        .select_related("product")
        .prefetch_related("lines__item")
        .order_by("run_date", "pk")
    )
    headers = [
        "Run", "Date", "Product", "Expected packets", "Good packets",
        "Yield variance %", "Yield flagged", "Material", "Unit",
        "Planned qty", "Used qty", "Wasted qty", "Variance %", "Flagged",
    ]
    rows = []
    for run in runs:
        variance = run.yield_variance_pct
        yield_flag = "Yes" if variance is None or abs(variance) > VARIANCE_TOLERANCE else "No"
        for line in run.lines.all():
            rows.append([
                f"#{run.pk}", day(run.run_date), run.product.name,
                run.expected_output, run.good_output, variance, yield_flag,
                line.item.name, line.item.unit, line.planned_qty,
                line.actual_qty, line.wasted_qty, line.variance_pct,
                "Yes" if line.flagged else "No",
            ])
    return {"headers": headers, "rows": rows, "totals": None}


def payments_register(start, end):
    payments = (
        Payment.objects.filter(payment_date__range=(start, end))
        .select_related("invoice", "invoice__customer", "received_by")
        .order_by("payment_date", "pk")
    )
    headers = ["Date", "Invoice", "Customer", "Amount", "Mode", "Reference", "Received by"]
    rows = [
        [
            day(p.payment_date), p.invoice.invoice_number, p.invoice.customer.name,
            p.amount, p.get_mode_display(), p.reference,
            p.received_by.username if p.received_by else "",
        ]
        for p in payments
    ]
    return {
        "headers": headers,
        "rows": rows,
        "totals": total_row(len(headers), "Total collected", rows, [3]),
    }


def outstanding_ageing(start, end):
    """What customers owe today, by age of invoice. The date range is not used."""
    customer_rows, grand = ageing_report()
    headers = ["Customer"] + BUCKET_LABELS + ["Total outstanding"]
    rows = [[r["customer"].name] + r["buckets"] + [r["total"]] for r in customer_rows]
    totals = ["All customers"] + grand["buckets"] + [grand["total"]]
    return {"headers": headers, "rows": rows, "totals": totals}


ACCOUNTS = ("Admin", "Accountant", "Owner")
FLOOR = ACCOUNTS + ("Production",)

REPORTS = [
    {"slug": "sales-register", "title": "Sales register", "build": sales_register, "roles": ACCOUNTS, "dated": True},
    {"slug": "sales-by-customer", "title": "Customer-wise sales", "build": sales_by_customer, "roles": ACCOUNTS, "dated": True},
    {"slug": "sales-by-product", "title": "Product-wise sales", "build": sales_by_product, "roles": ACCOUNTS, "dated": True},
    {"slug": "gst-summary", "title": "GST summary of outward supplies (GSTR-3B / GSTR-1 shape)", "build": gst_summary, "roles": ACCOUNTS, "dated": True},
    {"slug": "hsn-summary", "title": "HSN-wise summary (GSTR-1 table 12 shape)", "build": hsn_summary, "roles": ACCOUNTS, "dated": True},
    {"slug": "purchase-register", "title": "Purchase register", "build": purchase_register, "roles": ACCOUNTS, "dated": True},
    {"slug": "stock-summary", "title": "Stock summary (raw, packaging, finished goods)", "build": stock_summary, "roles": FLOOR, "dated": True},
    {"slug": "stock-ledger", "title": "Stock ledger", "build": stock_ledger, "roles": FLOOR, "dated": True},
    {"slug": "production-report", "title": "Production: planned vs actual consumption, yield and wastage", "build": production_report, "roles": FLOOR, "dated": True},
    {"slug": "payments-register", "title": "Payments and collections", "build": payments_register, "roles": ACCOUNTS, "dated": True},
    {"slug": "outstanding-ageing", "title": "Outstanding receivables with ageing", "build": outstanding_ageing, "roles": ACCOUNTS, "dated": False},
]
REPORT_BY_SLUG = {r["slug"]: r for r in REPORTS}