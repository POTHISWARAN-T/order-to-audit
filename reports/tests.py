from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from billing.models import Payment
from billing.receivables import record_payment
from billing.services import create_invoice, dispatch_invoice
from masters.benchmark_helpers import item, make_benchmark_run, seed
from masters.models import Customer
from sales.models import Order, OrderLine

from .builders import REPORTS, gst_summary, outstanding_ageing, sales_register, stock_summary


class ReportTests(TestCase):
    def setUp(self):
        seed()
        call_command("setup_roles", stdout=StringIO())
        make_benchmark_run()
        admin = User.objects.get(username="factory_admin")
        murukku = item("Murukku 200 g")
        order = Order.objects.create(
            customer=Customer.objects.get(name="Retailer A"),
            salesman=User.objects.get(username="salesman_a"),
        )
        OrderLine.objects.create(order=order, product=murukku, quantity=150, rate=murukku.rate)
        order.status = Order.APPROVED
        order.save()
        invoice = create_invoice(order, admin)
        dispatch_invoice(invoice, admin)
        record_payment(invoice, Decimal("4000.00"), date.today(), Payment.CASH, "", admin)
        self.today = timezone.localdate()
        self.start = self.today.replace(day=1)

    def test_every_report_opens_in_every_format(self):
        self.client.login(username="accountant", password="Demo@12345")
        for report in REPORTS:
            for fmt in ("html", "csv", "xlsx", "pdf"):
                with self.subTest(report=report["slug"], fmt=fmt):
                    url = f"/reports/{report['slug']}/?format={fmt}"
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_a_salesman_cannot_open_a_report(self):
        self.client.login(username="salesman_a", password="Demo@12345")
        self.assertEqual(self.client.get("/reports/sales-register/").status_code, 403)

    def test_stock_summary_shows_opening_receipts_issues_and_closing(self):
        rows = {r[0]: r for r in stock_summary(self.start, self.today)["rows"]}
        expected = {
            "Flour": ("100", "60", "40", "120"),
            "200 g pouch": ("500", "0", "194", "306"),
            "Murukku 200 g": ("50", "188", "150", "88"),
        }
        for name, figures in expected.items():
            row = rows[name]
            for column, value in zip(row[3:7], figures):
                self.assertEqual(column, Decimal(value), name)

    def test_sales_gst_and_ageing_reports_show_the_benchmark_figures(self):
        sales = sales_register(self.start, self.today)
        self.assertEqual(sales["totals"][9], Decimal("7875.00"))
        gst = gst_summary(self.start, self.today)
        self.assertEqual(gst["totals"][4], Decimal("187.50"))
        self.assertEqual(gst["totals"][5], Decimal("187.50"))
        ageing = outstanding_ageing(self.start, self.today)
        self.assertEqual(ageing["rows"][0][5], Decimal("3875.00"))