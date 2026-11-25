from decimal import Decimal

from django.db import transaction

from inventory.models import StockMovement
from masters.models import BOM, BOMLine

# A variance bigger than this percentage (up or down) is flagged
VARIANCE_TOLERANCE = Decimal("3")


def pct_variance(planned, actual):
    """(actual - planned) / planned * 100, rounded to 2 places. None if planned is 0."""
    if planned == 0:
        return None
    return ((actual - planned) / planned * 100).quantize(Decimal("0.01"))


def is_flagged(variance):
    return variance is None or abs(variance) > VARIANCE_TOLERANCE


@transaction.atomic
def post_production_run(run):
    """Post a saved run to the stock ledger and work out the variances."""
    bom = BOM.objects.get(product=run.product)
    ref = f"Production run #{run.pk}"

    # 1. Yield: expected vs actual packets
    run.expected_output = Decimal(bom.expected_yield) * run.batches
    run.yield_variance_pct = pct_variance(run.expected_output, Decimal(run.good_output))
    run.posted = True
    run.save()

    # 2. Materials: planned vs actual, and take them out of stock
    for line in run.lines.select_related("item"):
        bom_line = BOMLine.objects.filter(bom=bom, item=line.item).first()
        line.planned_qty = bom_line.qty_per_batch * run.batches if bom_line else Decimal("0")
        consumed = line.actual_qty + line.wasted_qty
        line.variance_pct = pct_variance(line.planned_qty, consumed)
        line.flagged = is_flagged(line.variance_pct)
        line.save()

        if line.actual_qty > 0:
            StockMovement.objects.create(
                item=line.item,
                quantity=-line.actual_qty,
                movement_type=StockMovement.PRODUCTION_ISSUE,
                source_ref=ref,
                created_by=run.created_by,
            )
        if line.wasted_qty > 0:
            StockMovement.objects.create(
                item=line.item,
                quantity=-line.wasted_qty,
                movement_type=StockMovement.WASTAGE,
                source_ref=ref,
                created_by=run.created_by,
            )

    # 3. Finished goods go up
    StockMovement.objects.create(
        item=run.product,
        quantity=Decimal(run.good_output),
        movement_type=StockMovement.PRODUCTION_OUTPUT,
        source_ref=ref,
        created_by=run.created_by,
    )