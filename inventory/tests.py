from decimal import Decimal

from django.test import TestCase

from masters.benchmark_helpers import buy_flour, item, seed
from masters.models import Item

from .models import StockMovement
from .services import get_balance


class LedgerTests(TestCase):
    def setUp(self):
        seed()

    def test_opening_balances_come_from_the_ledger(self):
        expected = {
            "Flour": "100",
            "Cooking oil": "30",
            "Salt and spice mix": "5",
            "200 g pouch": "500",
            "Carton (20 packets)": "30",
            "Murukku 200 g": "50",
        }
        for name, qty in expected.items():
            self.assertEqual(get_balance(item(name)), Decimal(qty), name)

    def test_loading_the_seed_twice_does_not_double_the_stock(self):
        seed()
        opening_rows = StockMovement.objects.filter(movement_type=StockMovement.OPENING)
        self.assertEqual(opening_rows.count(), 6)
        self.assertEqual(get_balance(item("Flour")), Decimal("100"))

    def test_purchase_adds_to_stock_and_links_to_its_source(self):
        purchase = buy_flour()
        self.assertEqual(get_balance(item("Flour")), Decimal("160"))
        movement = StockMovement.objects.get(movement_type=StockMovement.PURCHASE)
        self.assertEqual(movement.quantity, Decimal("60"))
        self.assertEqual(movement.source_ref, f"Purchase #{purchase.pk}")
        self.assertEqual(purchase.amount, Decimal("2700.00"))

    def test_an_item_with_no_movements_has_zero_stock(self):
        spare = Item.objects.create(name="Test item", item_type=Item.RAW, unit="kg")
        self.assertEqual(get_balance(spare), Decimal("0"))