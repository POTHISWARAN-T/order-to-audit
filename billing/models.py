from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from masters.models import Customer, Item
from sales.models import Order


class Invoice(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="invoice")
    fin_year = models.CharField(max_length=7)  # e.g. 2026-27
    sequence = models.PositiveIntegerField()
    invoice_number = models.CharField(max_length=20, unique=True)
    invoice_date = models.DateField(default=timezone.localdate)

    # Customer details are copied here, so later edits never change a posted invoice
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    customer_gstin = models.CharField(max_length=15, blank=True)
    place_of_supply = models.CharField(max_length=50)
    is_interstate = models.BooleanField(default=False)  # True means IGST

    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fin_year", "sequence"], name="unique_invoice_per_year"
            )
        ]

    @property
    def gst_total(self):
        return self.cgst + self.sgst + self.igst

    def __str__(self):
        return self.invoice_number


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Item, on_delete=models.PROTECT)
    description = models.CharField(max_length=150)
    hsn_code = models.CharField(max_length=10, blank=True)
    quantity = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    @property
    def line_total(self):
        return self.taxable_value + self.cgst + self.sgst + self.igst
    
class Payment(models.Model):
    CASH = "CASH"
    UPI = "UPI"
    BANK = "BANK"
    CHEQUE = "CHEQUE"
    MODES = [(CASH, "Cash"), (UPI, "UPI"), (BANK, "Bank transfer"), (CHEQUE, "Cheque")]

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    mode = models.CharField(max_length=8, choices=MODES, default=CASH)
    reference = models.CharField(max_length=60, blank=True)  # UPI id, cheque number
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Rs {self.amount} against {self.invoice}"   
    
class CreditNote(models.Model):
    invoice = models.OneToOneField(Invoice, on_delete=models.PROTECT, related_name="credit_note")
    fin_year = models.CharField(max_length=7)
    sequence = models.PositiveIntegerField()
    credit_note_number = models.CharField(max_length=20, unique=True)
    note_date = models.DateField(default=timezone.localdate)
    reason = models.CharField(max_length=200)
    goods_returned = models.BooleanField(default=False)

    # Amounts copied from the invoice: a full credit note reverses all of it
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2)
    cgst = models.DecimalField(max_digits=12, decimal_places=2)
    sgst = models.DecimalField(max_digits=12, decimal_places=2)
    igst = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fin_year", "sequence"], name="unique_credit_note_per_year"
            )
        ]

    def __str__(self):
        return self.credit_note_number    