import csv
import re
from io import BytesIO
from xml.sax.saxutils import escape

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def csv_response(data, filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    response.write("\ufeff")  # lets Excel read the file as UTF-8
    writer = csv.writer(response)
    writer.writerow(data["headers"])
    writer.writerows(data["rows"])
    if data["totals"]:
        writer.writerow(data["totals"])
    return response


def xlsx_response(data, title, filename):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = re.sub(r"[\[\]:*?/\\]", "-", title)[:31]
    sheet.append(data["headers"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in data["rows"]:
        sheet.append(row)
    if data["totals"]:
        sheet.append(data["totals"])
        for cell in sheet[sheet.max_row]:
            cell.font = Font(bold=True)
    for index, column in enumerate(sheet.columns, start=1):
        longest = max(len(str(cell.value if cell.value is not None else "")) for cell in column)
        sheet.column_dimensions[get_column_letter(index)].width = min(longest + 2, 40)

    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response


def pdf_response(data, title, period, filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=7, leading=9)
    head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold")

    table_rows = [[Paragraph(escape(str(h)), head) for h in data["headers"]]]
    for row in data["rows"]:
        table_rows.append([Paragraph(escape(str(c)), cell) for c in row])
    if data["totals"]:
        table_rows.append([Paragraph(f"<b>{escape(str(c))}</b>", cell) for c in data["totals"]])

    width = (297 - 20) * mm / len(data["headers"])
    table = Table(table_rows, colWidths=[width] * len(data["headers"]), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story = [Paragraph(escape(title), styles["Title"]), Paragraph(escape(period), styles["BodyText"]), Spacer(1, 4 * mm)]
    if not data["rows"]:
        story.append(Paragraph("No records in this period.", styles["BodyText"]))
    story.append(table)
    doc.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response