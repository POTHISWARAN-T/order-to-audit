from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from billing.models import Payment
from billing.receivables import record_payment
from billing.services import create_invoice, dispatch_invoice
from masters.benchmark_helpers import item, make_benchmark_run, seed
from masters.models import Customer
from production.models import RunOverhead
from sales.models import Order, OrderLine


class DashboardTests(TestCase):
    def setUp(self):
        seed()
        call_command("setup_roles", stdout=StringIO())
        run = make_benchmark_run()
        RunOverhead.objects.create(run=run, kind=RunOverhead.LABOUR, amount=Decimal("1200"))
        RunOverhead.objects.create(run=run, kind=RunOverhead.GAS, amount=Decimal("600"))

        admin = User.objects.get(username="factory_admin")
        seller = User.objects.get(username="salesman_a")
        murukku = item("Murukku 200 g")

        order_a = Order.objects.create(
            customer=Customer.objects.get(name="Retailer A"),
            salesman=seller,
            status=Order.APPROVED,
        )
        OrderLine.objects.create(order=order_a, product=murukku, quantity=150, rate=murukku.rate)
        invoice = create_invoice(order_a, admin)
        dispatch_invoice(invoice, admin)
        record_payment(invoice, Decimal("4000.00"), date.today(), Payment.CASH, "", admin)

        order_b = Order.objects.create(
            customer=Customer.objects.get(name="Distributor B"), salesman=seller
        )
        OrderLine.objects.create(order=order_b, product=murukku, quantity=120, rate=murukku.rate)

    def open_dashboard(self, username="owner"):
        self.client.login(username=username, password="Demo@12345")
        return self.client.get("/dashboard/")

    def test_owner_sees_the_money_figures(self):
        response = self.open_dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["net_sales"], Decimal("7500.00"))
        self.assertEqual(response.context["collected"], Decimal("4000.00"))
        self.assertEqual(response.context["dues"]["total"], Decimal("3875.00"))
        self.assertEqual(response.context["dues"]["overdue"], Decimal("0.00"))
        self.assertEqual(response.context["dues"]["top"][0]["customer"].name, "Retailer A")

    def test_owner_sees_todays_orders(self):
        response = self.open_dashboard()
        today = response.context["orders_today"]
        self.assertEqual(today["count"], 2)
        self.assertEqual(today["value"], Decimal("13500.00"))
        self.assertEqual(response.context["waiting"], 1)

    def test_variance_alerts_show_yield_oil_and_cartons_but_not_pouches(self):
        alerts = self.open_dashboard().context["alerts"]
        by_name = {a["what"]: a["variance_text"] for a in alerts}
        self.assertEqual(by_name["Yield"], "-6.00")
        self.assertEqual(by_name["Cooking oil"], "+5.00")
        self.assertEqual(by_name["Carton (20 packets)"], "-10.00")
        self.assertNotIn("200 g pouch", by_name)
        self.assertNotIn("Flour", by_name)

    def test_cost_per_packet_and_margin(self):
        summary = self.open_dashboard().context["summary"][0]
        self.assertEqual(summary["cost_per_packet"], Decimal("31.1436"))
        self.assertEqual(summary["margin_pct"], Decimal("37.71"))

    def test_stock_levels_show_finished_goods_after_dispatch(self):
        rows = {r["item"].name: r for r in self.open_dashboard().context["stock_rows"]}
        self.assertEqual(rows["Murukku 200 g"]["balance"], Decimal("88"))
        self.assertEqual(rows["Murukku 200 g"]["free"], Decimal("88"))
        self.assertEqual(rows["Flour"]["balance"], Decimal("120"))
        self.assertIsNone(rows["Flour"]["free"])

    def test_who_may_open_the_dashboard(self):
        for username in ("owner", "accountant", "factory_admin"):
            self.assertEqual(self.open_dashboard(username).status_code, 200, username)
        for username in ("salesman_a", "production_sup"):
            self.assertEqual(self.open_dashboard(username).status_code, 403, username)