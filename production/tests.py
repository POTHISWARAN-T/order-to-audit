from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from inventory.services import get_balance
from masters.benchmark_helpers import item, make_benchmark_run, seed

from .costing import run_cost, weighted_average_rate
from .models import RunOverhead
from .services import is_flagged, pct_variance


class VarianceMathTests(TestCase):
    def test_variance_percentage(self):
        self.assertEqual(pct_variance(Decimal("200"), Decimal("188")), Decimal("-6.00"))
        self.assertEqual(pct_variance(Decimal("10"), Decimal("10.5")), Decimal("5.00"))

    def test_a_zero_plan_has_no_percentage(self):
        self.assertIsNone(pct_variance(Decimal("0"), Decimal("5")))

    def test_tolerance_is_three_percent_either_way(self):
        self.assertFalse(is_flagged(Decimal("3.00")))
        self.assertFalse(is_flagged(Decimal("-3.00")))
        self.assertTrue(is_flagged(Decimal("3.01")))
        self.assertTrue(is_flagged(Decimal("-3.01")))
        self.assertTrue(is_flagged(None))


class BenchmarkProductionTests(TestCase):
    def setUp(self):
        seed()
        self.run = make_benchmark_run()

    def test_closing_stock_matches_the_problem_statement(self):
        expected = {
            "Flour": "120",
            "Cooking oil": "19.5",
            "Salt and spice mix": "3.8",
            "200 g pouch": "306",
            "Carton (20 packets)": "21",
            "Murukku 200 g": "238",
        }
        for name, qty in expected.items():
            self.assertEqual(get_balance(item(name)), Decimal(qty), name)

    def test_yield_variance_is_minus_six_percent_and_flagged(self):
        self.run.refresh_from_db()
        self.assertEqual(self.run.expected_output, Decimal("200"))
        self.assertEqual(self.run.yield_variance_pct, Decimal("-6.00"))
        self.assertTrue(is_flagged(self.run.yield_variance_pct))

    def test_oil_is_five_percent_over_and_flagged(self):
        line = self.run.lines.get(item=item("Cooking oil"))
        self.assertEqual(line.planned_qty, Decimal("10"))
        self.assertEqual(line.variance_pct, Decimal("5.00"))
        self.assertTrue(line.flagged)

    def test_pouches_count_the_damaged_ones_and_stay_within_tolerance(self):
        line = self.run.lines.get(item=item("200 g pouch"))
        self.assertEqual(line.variance_pct, Decimal("-3.00"))
        self.assertFalse(line.flagged)

    def test_flour_matches_the_plan(self):
        line = self.run.lines.get(item=item("Flour"))
        self.assertEqual(line.variance_pct, Decimal("0.00"))
        self.assertFalse(line.flagged)


class CostingTests(TestCase):
    def setUp(self):
        seed()
        self.run = make_benchmark_run()
        RunOverhead.objects.create(run=self.run, kind=RunOverhead.LABOUR, amount=Decimal("1200"))
        RunOverhead.objects.create(run=self.run, kind=RunOverhead.GAS, amount=Decimal("600"))

    def test_flour_is_valued_at_the_weighted_average(self):
        later = timezone.now() + timedelta(days=1)
        self.assertEqual(weighted_average_rate(item("Flour"), later), Decimal("43.125"))

    def test_cost_per_packet_and_margin(self):
        cost = run_cost(self.run)
        self.assertEqual(cost["material_total"], Decimal("4055.00"))
        self.assertEqual(cost["overhead_total"], Decimal("1800.00"))
        self.assertEqual(cost["total_cost"], Decimal("5855.00"))
        self.assertEqual(cost["cost_per_packet"], Decimal("31.1436"))
        self.assertEqual(cost["margin"], Decimal("18.8564"))
        self.assertEqual(cost["margin_pct"], Decimal("37.71"))

    def test_a_negative_overhead_corrects_an_earlier_entry(self):
        RunOverhead.objects.create(run=self.run, kind=RunOverhead.OTHER, amount=Decimal("-100"))
        self.assertEqual(run_cost(self.run)["overhead_total"], Decimal("1700.00"))