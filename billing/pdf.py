from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def pct(value):
    """5.00 becomes '5' and 2.50 becomes '2.5'."""
    return format(value.normalize(), "f")


def build_invoice_pdf(invoice):
    """Return the tax invoice as PDF bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=invoice.invoice_number,
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=9, leading=12)
    interstate = invoice.is_interstate

    seller = (
        f"<b>{escape(settings.COMPANY_NAME)}</b><br/>{escape(settings.COMPANY_ADDRESS)}<br/>"
        f"GSTIN: {escape(settings.COMPANY_GSTIN)}<br/>State: {escape(settings.COMPANY_STATE)}"
    )
    meta = (
        f"Invoice No: <b>{escape(invoice.invoice_number)}</b><br/>"
        f"Date: {invoice.invoice_date:%d-%m-%Y}<br/>Order: ORD-{invoice.order_id}"
    )
    buyer = (
        f"<b>Bill to: {escape(invoice.customer.name)}</b><br/>"
        f"GSTIN: {escape(invoice.customer_gstin or 'Unregistered')}<br/>"
        f"Place of supply: {escape(invoice.place_of_supply)}"
    )
    supply = "Inter-state supply (IGST)" if interstate else "Intra-state supply (CGST + SGST)"

    top = Table(
        [
            [Paragraph(seller, small), Paragraph(meta, small)],
            [Paragraph(buyer, small), Paragraph(supply, small)],
        ],
        colWidths=[100 * mm, 86 * mm],
    )
    top.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    header = ["#", "Description", "HSN", "Qty", "Rate", "Taxable"]
    header += ["IGST"] if interstate else ["CGST", "SGST"]
    header.append("Total")
    rows = [header]
    for number, line in enumerate(invoice.lines.all(), start=1):
        row = [
            number,
            Paragraph(escape(line.description), small),
            line.hsn_code,
            line.quantity,
            f"{line.rate:.2f}",
            f"{line.taxable_value:.2f}",
        ]
        if interstate:
            row.append(f"{line.igst:.2f} ({pct(line.gst_rate)}%)")
        else:
            half = pct(line.gst_rate / 2)
            row.append(f"{line.cgst:.2f} ({half}%)")
            row.append(f"{line.sgst:.2f} ({half}%)")
        row.append(f"{line.line_total:.2f}")
        rows.append(row)

    widths = [8, 44, 20, 12, 16, 24, 32, 28] if interstate else [8, 34, 18, 10, 14, 20, 26, 26, 24]
    items = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1)
    items.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ]
        )
    )

    totals = [["Taxable value", f"Rs {invoice.taxable_value:.2f}"]]
    if interstate:
        totals.append(["IGST", f"Rs {invoice.igst:.2f}"])
    else:
        totals.append(["CGST", f"Rs {invoice.cgst:.2f}"])
        totals.append(["SGST", f"Rs {invoice.sgst:.2f}"])
    totals.append(["Invoice total", f"Rs {invoice.total_amount:.2f}"])
    totals_table = Table(totals, colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )

    story = [
        Paragraph("TAX INVOICE", styles["Title"]),
        top,
        Spacer(1, 6 * mm),
        items,
        Spacer(1, 4 * mm),
        totals_table,
        Spacer(1, 8 * mm),
        Paragraph("This is a computer-generated invoice.", small),
    ]
    doc.build(story)
    return buffer.getvalue()