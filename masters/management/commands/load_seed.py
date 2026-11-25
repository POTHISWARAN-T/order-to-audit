from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from masters.models import BOM, BOMLine, Customer, Item, Supplier


class Command(BaseCommand):
    help = "Load the benchmark master data (section 5 of the problem statement)"

    @transaction.atomic
    def handle(self, *args, **options):
        def make_item(name, kind, unit, rate, hsn=""):
            obj, _ = Item.objects.update_or_create(
                name=name,
                defaults={
                    "item_type": kind,
                    "unit": unit,
                    "rate": Decimal(rate),
                    "hsn_code": hsn,
                },
            )
            return obj

        flour = make_item("Flour", Item.RAW, "kg", "42")
        oil = make_item("Cooking oil", Item.RAW, "litre", "140")
        spice = make_item("Salt and spice mix", Item.RAW, "kg", "200")
        pouch = make_item("200 g pouch", Item.PACKING, "piece", "2.50")
        carton = make_item("Carton (20 packets)", Item.PACKING, "piece", "15")
        murukku = make_item("Murukku 200 g", Item.FINISHED, "packet", "50", "21069099")

        bom, _ = BOM.objects.update_or_create(
            product=murukku, defaults={"expected_yield": 200}
        )
        recipe = [
            (flour, "40"),
            (oil, "10"),
            (spice, "1.2"),
            (pouch, "200"),
            (carton, "10"),
        ]
        for item, qty in recipe:
            BOMLine.objects.update_or_create(
                bom=bom, item=item, defaults={"qty_per_batch": Decimal(qty)}
            )

        Customer.objects.get_or_create(
            name="Retailer A",
            defaults={"state": "Tamil Nadu", "gstin": "33ABCDE1234F1Z5"},
        )
        Customer.objects.get_or_create(
            name="Distributor B",
            defaults={"state": "Karnataka", "gstin": "29ABCDE5678G1Z3"},
        )
        Supplier.objects.get_or_create(
            name="Sample Flour Mills", defaults={"gstin": "33PQRST1234L1Z8"}
        )

        self.stdout.write(self.style.SUCCESS("Seed data loaded."))