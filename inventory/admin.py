from django.contrib import admin

from .models import Purchase, StockMovement
from .services import post_purchase


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "item", "movement_type", "quantity", "source_ref")
    list_filter = ("movement_type", "item")
    exclude = ("created_by",)

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # A ledger is never edited or deleted. Mistakes are fixed with a new adjustment row.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("purchase_date", "supplier", "item", "quantity", "rate", "bill_number")
    list_filter = ("supplier", "item")
    exclude = ("created_by",)

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        super().save_model(request, obj, form, change)
        post_purchase(obj)

    # A saved purchase is final, because it has already posted to the ledger.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False