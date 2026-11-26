from decimal import ROUND_HALF_UP, Decimal

from inventory.models import Purchase, StockMovement

PAISA = Decimal("0.01")
FOUR = Decimal("0.0001")
ZERO = Decimal("0.00")


def money(value):
    return value.quantize(PAISA, rounding=ROUND_HALF_UP)


def weighted_average_rate(item, before):
    """Weighted-average rate of an item just before the given time.

    Opening stock and other plus-movements come in at the item's rate, purchases at
    their own rate, and issues take stock out at the current average, which leaves
    the average unchanged.
    """
    events = []
    others = StockMovement.objects.filter(item=item, created_at__lt=before)
    for movement in others.exclude(movement_type=StockMovement.PURCHASE):
        rate = item.rate if movement.quantity > 0 else None
        events.append((movement.created_at, movement.quantity, rate))
    for purchase in Purchase.objects.filter(item=item, created_at__lt=before):
        events.append((purchase.created_at, purchase.quantity, purchase.rate))
    events.sort(key=lambda event: event[0])

    qty = Decimal("0")
    average = item.rate
    for _, change, rate in events:
        if change > 0:
            on_hand = max(qty, Decimal("0"))
            average = (on_hand * average + change * rate) / (on_hand + change)
        qty += change
    return average


def margin_figures(price, cost_per_packet):
    """Margin per packet and margin as a percentage of the selling price."""
    if cost_per_packet is None:
        return None, None
    margin = (price - cost_per_packet).quantize(FOUR, rounding=ROUND_HALF_UP)
    margin_pct = None
    if price:
        margin_pct = (margin / price * 100).quantize(PAISA, rounding=ROUND_HALF_UP)
    return margin, margin_pct


def run_cost(run):
    """Cost of one production run, with the working shown line by line."""
    materials = []
    material_total = ZERO
    for line in run.lines.all():
        used = line.actual_qty + line.wasted_qty  # damaged items are a cost too
        rate = weighted_average_rate(line.item, run.created_at)
        cost = money(used * rate)
        materials.append({"line": line, "used": used, "rate": rate, "cost": cost})
        material_total += cost

    overheads = list(run.overheads.all())
    overhead_total = sum((o.amount for o in overheads), ZERO)
    total_cost = material_total + overhead_total

    good = run.good_output
    cost_per_packet = None
    if good:
        cost_per_packet = (total_cost / good).quantize(FOUR, rounding=ROUND_HALF_UP)
    price = run.product.rate
    margin, margin_pct = margin_figures(price, cost_per_packet)

    return {
        "run": run,
        "materials": materials,
        "material_total": material_total,
        "overheads": overheads,
        "overhead_total": overhead_total,
        "total_cost": total_cost,
        "cost_per_packet": cost_per_packet,
        "price": price,
        "margin": margin,
        "margin_pct": margin_pct,
    }


def product_summary(costs):
    """Average cost per packet for each product across all of its runs."""
    totals = {}
    for c in costs:
        run = c["run"]
        row = totals.setdefault(
            run.product_id, {"product": run.product, "cost": ZERO, "packets": 0, "runs": 0}
        )
        row["cost"] += c["total_cost"]
        row["packets"] += run.good_output
        row["runs"] += 1

    summary = []
    for row in totals.values():
        per_packet = None
        if row["packets"]:
            per_packet = (row["cost"] / row["packets"]).quantize(FOUR, rounding=ROUND_HALF_UP)
        price = row["product"].rate
        margin, margin_pct = margin_figures(price, per_packet)
        summary.append(
            {**row, "cost_per_packet": per_packet, "price": price,
             "margin": margin, "margin_pct": margin_pct}
        )
    return sorted(summary, key=lambda r: r["product"].name)