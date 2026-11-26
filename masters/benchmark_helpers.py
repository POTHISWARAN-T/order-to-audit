from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from inventory.models import Purchase
from inventory.services import post_purchase
from masters.models import Item, Supplier
from production.models import ProductionRun, ProductionRunLine
from production.services import post_production_run


def seed():
    """Load the section 5 master data and opening stock."""
    call_command("load_seed", stdout=StringIO())


def item(name):
    return Item.objects.get(name=name)


def buy_flour():
    """Benchmark step 1: 60 kg of flour at Rs 45."""
    purchase = Purchase.objects.create(
        supplier=Supplier.objects.get(name="Sample Flour Mills"),
        item=item("Flour"),
        quantity=Decimal("60"),
        rate=Decimal("45"),
    )
    post_purchase(purchase)
    return purchase


def make_benchmark_run():
    """Benchmark steps 1 to 3: the flour purchase, then one production run."""
    buy_flour()
    run = ProductionRun.objects.create(
        product=item("Murukku 200 g"),
        batches=Decimal("1"),
        good_output=188,
        created_at=timezone.now() + timedelta(minutes=1),
    )
    lines = [
        ("Flour", "40", "0"),
        ("Cooking oil", "10.5", "0"),
        ("Salt and spice mix", "1.2", "0"),
        ("200 g pouch", "188", "6"),
        ("Carton (20 packets)", "9", "0"),
    ]
    for name, used, wasted in lines:
        ProductionRunLine.objects.create(
            run=run, item=item(name), actual_qty=Decimal(used), wasted_qty=Decimal(wasted)
        )
    post_production_run(run)
    return run