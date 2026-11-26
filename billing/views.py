from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from masters.permissions import role_required
from sales.models import Order

from .models import Invoice
from .pdf import build_invoice_pdf
from .services import create_invoice, dispatch_invoice


@role_required("Admin")
def billing_home(request):
    waiting = (
        Order.objects.filter(status=Order.APPROVED)
        .select_related("customer")
        .prefetch_related("lines__product")
        .order_by("created_at")
    )
    invoices = Invoice.objects.select_related("customer").order_by("-created_at")
    return render(
        request, "billing/billing_home.html", {"waiting": waiting, "invoices": invoices}
    )


@role_required("Admin")
@require_POST
def invoice_create(request, order_pk):
    order = get_object_or_404(Order, pk=order_pk)
    try:
        invoice = create_invoice(order, request.user)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("billing_home")
    return redirect("invoice_detail", pk=invoice.pk)


@role_required("Admin")
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("customer", "order"), pk=pk
    )
    text = (
        f"Invoice {invoice.invoice_number} from {settings.COMPANY_NAME}: "
        f"Rs {invoice.total_amount} for order ORD-{invoice.order_id}. "
        "The PDF is attached."
    )
    context = {
        "invoice": invoice,
        "lines": invoice.lines.select_related("product"),
        "company": {
            "name": settings.COMPANY_NAME,
            "address": settings.COMPANY_ADDRESS,
            "gstin": settings.COMPANY_GSTIN,
        },
        "whatsapp_url": "https://wa.me/?text=" + quote(text),
        "email_url": (
            "mailto:?subject=" + quote(f"Invoice {invoice.invoice_number}")
            + "&body=" + quote(text)
        ),
    }
    return render(request, "billing/invoice_detail.html", context)


@role_required("Admin")
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("customer"), pk=pk)
    response = HttpResponse(build_invoice_pdf(invoice), content_type="application/pdf")
    filename = invoice.invoice_number.replace("/", "-") + ".pdf"
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@role_required("Admin")
@require_POST
def invoice_dispatch(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        dispatch_invoice(invoice, request.user)
        messages.success(request, "Dispatched. Finished-goods stock has been reduced.")
    except ValueError as error:
        messages.error(request, str(error))
    return redirect("invoice_detail", pk=invoice.pk)