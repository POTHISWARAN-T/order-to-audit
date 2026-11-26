from decimal import Decimal

from django.db import models


class Item(models.Model):
    RAW = "RAW"
    PACKING = "PACK"
    FINISHED = "FG"
    TYPES = [(RAW, "Raw material"), (PACKING, "Packaging"), (FINISHED, "Finished good")]

    name = models.CharField(max_length=100, unique=True)
    item_type = models.CharField(max_length=4, choices=TYPES)
    unit = models.CharField(max_length=20)  # kg, litre, piece, packet
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=10, blank=True)
    gst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00"), help_text="GST %"
    )

    def __str__(self):
        return self.name


class BOM(models.Model):
    product = models.OneToOneField(Item, on_delete=models.PROTECT,
                                   limit_choices_to={"item_type": "FG"})
    expected_yield = models.PositiveIntegerField(help_text="Packets per batch")

    def __str__(self):
        return f"BOM: {self.product.name}"


class BOMLine(models.Model):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty_per_batch = models.DecimalField(max_digits=10, decimal_places=3)


class Customer(models.Model):
    name = models.CharField(max_length=150)
    state = models.CharField(max_length=50)  # decides CGST+SGST or IGST
    gstin = models.CharField(max_length=15, blank=True)


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    gstin = models.CharField(max_length=15, blank=True)