from django.contrib import admin

from .models import Invoice, InvoiceLine


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    inlines = [InvoiceLineInline]
    list_display = (
        "invoice_number", "invoice_date", "customer",
        "taxable_value", "total_amount", "dispatched_at",
    )
    list_filter = ("fin_year", "is_interstate")

    # A posted invoice is never edited or deleted. Cancelling uses a credit note (Phase 12).
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False