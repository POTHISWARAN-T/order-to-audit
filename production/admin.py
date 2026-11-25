from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from inventory.services import get_balance

from .models import ProductionRun, ProductionRunLine
from .services import VARIANCE_TOLERANCE, post_production_run


class RunLineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        for form in self.forms:
            data = form.cleaned_data
            if not data or data.get("DELETE"):
                continue
            item = data.get("item")
            used = (data.get("actual_qty") or 0) + (data.get("wasted_qty") or 0)
            if item and used > get_balance(item):
                raise ValidationError(
                    f"Not enough {item.name} in stock. Available: {get_balance(item)} {item.unit}."
                )


class ProductionRunLineInline(admin.TabularInline):
    model = ProductionRunLine
    formset = RunLineFormSet
    extra = 5
    fields = ("item", "actual_qty", "wasted_qty", "planned_qty", "variance_pct", "flagged")
    readonly_fields = ("planned_qty", "variance_pct", "flagged")


@admin.register(ProductionRun)
class ProductionRunAdmin(admin.ModelAdmin):
    inlines = [ProductionRunLineInline]
    fields = (
        "product", "batches", "good_output", "run_date", "notes",
        "expected_output", "yield_variance_pct",
    )
    readonly_fields = ("expected_output", "yield_variance_pct")
    list_display = (
        "id", "run_date", "product", "expected_output",
        "good_output", "yield_variance_pct", "yield_ok",
    )

    @admin.display(boolean=True, description="Yield OK?")
    def yield_ok(self, obj):
        if obj.yield_variance_pct is None:
            return None
        return abs(obj.yield_variance_pct) <= VARIANCE_TOLERANCE

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # The material lines are saved now, so the run can be posted to the ledger
        post_production_run(form.instance)

    # A posted run is final. Mistakes are fixed with an adjustment in the ledger.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False