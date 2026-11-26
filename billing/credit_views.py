from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from masters.permissions import role_required

from .credit import issue_credit_note
from .models import CreditNote, Invoice
from .receivables import outstanding, paid_amount


@role_required("Admin")
def credit_notes_home(request):
    invoices = (
        Invoice.objects.filter(credit_note__isnull=True)
        .select_related("customer")
        .prefetch_related("payments")
        .order_by("-created_at")
    )
    items = [{"invoice": i, "paid": paid_amount(i), "outstanding": outstanding(i)} for i in invoices]
    notes = CreditNote.objects.select_related("invoice", "invoice__customer").order_by("-created_at")
    return render(request, "billing/credit_notes_home.html", {"items": items, "notes": notes})


@role_required("Admin")
def credit_note_create(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("customer"), pk=pk)
    if request.method == "POST":
        try:
            note = issue_credit_note(
                invoice,
                request.POST.get("reason", ""),
                request.POST.get("goods_returned") == "on",
                request.user,
            )
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(
                request,
                f"Credit note {note.credit_note_number} issued for {invoice.invoice_number}.",
            )
            return redirect("credit_notes_home")
    return render(
        request,
        "billing/credit_note_form.html",
        {"invoice": invoice, "paid": paid_amount(invoice)},
    )