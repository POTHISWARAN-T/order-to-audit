from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from inventory.models import StockMovement
from inventory.services import get_balance
from masters.benchmark_helpers import item, make_benchmark_run, seed
from masters.models import Customer
from sales.models import Order, OrderLine

from .models import Invoice, Payment
from .receivables import ageing_report, bucket_index, outstanding, paid_amount, record_payment
from .services import create_invoice, dispatch_invoice, financial_year, line_tax, money


class TaxMathTests(TestCase):
    def test_tax_inside_the_state_is_split_into_cgst_and_sgst(self):
        result = line_tax(Decimal("7500.00"), Decimal("5.00"), False)
        self.assertEqual(result, (Decimal("187.50"), Decimal("187.50"), Decimal("0.00")))

    def test_tax_to_another_state_is_all_igst(self):
        result = line_tax(Decimal("7500.00"), Decimal("5.00"), True)
        self.assertEqual(result, (Decimal("0.00"), Decimal("0.00"), Decimal("375.00")))

    def test_money_rounds_half_up_to_the_paisa(self):
        self.assertEqual(money(Decimal("0.125")), Decimal("0.13"))
        self.assertEqual(money(Decimal("2.675")), Decimal("2.68"))

    def test_financial_year_runs_april_to_march(self):
        self.assertEqual(financial_year(date(2026, 4, 1)), "2026-27")
        self.assertEqual(financial_year(date(2026, 11, 26)), "2026-27")
        self.assertEqual(financial_year(date(2027, 3, 31)), "2026-27")
        self.assertEqual(financial_year(date(2027, 4, 1)), "2027-28")


class InvoiceTests(TestCase):
    def setUp(self):
        seed()
        make_benchmark_run()
        self.user = User.objects.create_user("biller", password="x")
        self.murukku = item("Murukku 200 g")

    def approved_order(self, customer_name, qty):
        order = Order.objects.create(
            customer=Customer.objects.get(name=customer_name), salesman=self.user
        )
        OrderLine.objects.create(
            order=order, product=self.murukku, quantity=qty, rate=self.murukku.rate
        )
        order.status = Order.APPROVED
        order.save()
        return order

    def test_retailer_a_invoice_matches_the_problem_statement(self):
        invoice = create_invoice(self.approved_order("Retailer A", 150), self.user)
        self.assertEqual(invoice.taxable_value, Decimal("7500.00"))
        self.assertEqual(invoice.cgst, Decimal("187.50"))
        self.assertEqual(invoice.sgst, Decimal("187.50"))
        self.assertEqual(invoice.igst, Decimal("0.00"))
        self.assertEqual(invoice.total_amount, Decimal("7875.00"))
        self.assertEqual(invoice.place_of_supply, "Tamil Nadu")
        self.assertFalse(invoice.is_interstate)
        self.assertTrue(invoice.invoice_number.endswith("/0001"))
        self.assertEqual(invoice.order.status, Order.INVOICED)

    def test_distributor_b_in_karnataka_is_charged_igst(self):
        invoice = create_invoice(self.approved_order("Distributor B", 120), self.user)
        self.assertTrue(invoice.is_interstate)
        self.assertEqual(invoice.taxable_value, Decimal("6000.00"))
        self.assertEqual(invoice.igst, Decimal("300.00"))
        self.assertEqual(invoice.cgst, Decimal("0.00"))
        self.assertEqual(invoice.sgst, Decimal("0.00"))
        self.assertEqual(invoice.total_amount, Decimal("6300.00"))

    def test_invoice_numbers_run_in_sequence_within_the_year(self):
        first = create_invoice(self.approved_order("Retailer A", 10), self.user)
        second = create_invoice(self.approved_order("Retailer A", 20), self.user)
        prefix = f"INV/{financial_year(timezone.localdate())}/"
        self.assertEqual(first.invoice_number, prefix + "0001")
        self.assertEqual(second.invoice_number, prefix + "0002")

    def test_only_an_approved_order_can_be_invoiced(self):
        order = Order.objects.create(
            customer=Customer.objects.get(name="Retailer A"), salesman=self.user
        )
        with self.assertRaises(ValueError):
            create_invoice(order, self.user)

    def test_a_posted_invoice_keeps_the_customer_details_it_was_raised_with(self):
        invoice = create_invoice(self.approved_order("Retailer A", 150), self.user)
        Customer.objects.filter(name="Retailer A").update(state="Kerala")
        invoice.refresh_from_db()
        self.assertEqual(invoice.place_of_supply, "Tamil Nadu")

    def test_dispatch_reduces_finished_goods_to_88(self):
        invoice = create_invoice(self.approved_order("Retailer A", 150), self.user)
        self.assertEqual(get_balance(self.murukku), Decimal("238"))
        dispatch_invoice(invoice, self.user)
        self.assertEqual(get_balance(self.murukku), Decimal("88"))
        movement = StockMovement.objects.get(movement_type=StockMovement.DISPATCH)
        self.assertEqual(movement.quantity, Decimal("-150"))
        self.assertEqual(movement.source_ref, invoice.invoice_number)
        invoice.order.refresh_from_db()
        self.assertEqual(invoice.order.status, Order.DISPATCHED)

    def test_an_invoice_cannot_be_dispatched_twice(self):
        invoice = create_invoice(self.approved_order("Retailer A", 150), self.user)
        dispatch_invoice(invoice, self.user)
        with self.assertRaises(ValueError):
            dispatch_invoice(invoice, self.user)
        self.assertEqual(get_balance(self.murukku), Decimal("88"))

    def test_dispatch_is_refused_when_the_stock_is_not_there(self):
        invoice = create_invoice(self.approved_order("Retailer A", 300), self.user)
        with self.assertRaises(ValueError):
            dispatch_invoice(invoice, self.user)
        self.assertEqual(get_balance(self.murukku), Decimal("238"))
        invoice.refresh_from_db()
        self.assertIsNone(invoice.dispatched_at)


class PaymentTests(TestCase):
    def setUp(self):
        seed()
        make_benchmark_run()
        self.user = User.objects.create_user("cashier", password="x")
        murukku = item("Murukku 200 g")
        order = Order.objects.create(
            customer=Customer.objects.get(name="Retailer A"),
            salesman=self.user,
            status=Order.APPROVED,
        )
        OrderLine.objects.create(order=order, product=murukku, quantity=150, rate=murukku.rate)
        self.invoice = create_invoice(order, self.user)

    def pay(self, amount):
        return record_payment(
            self.invoice, Decimal(amount), date.today(), Payment.CASH, "", self.user
        )

    def test_a_payment_of_4000_leaves_3875_outstanding(self):
        self.pay("4000.00")
        self.assertEqual(paid_amount(self.invoice), Decimal("4000.00"))
        self.assertEqual(outstanding(self.invoice), Decimal("3875.00"))

    def test_paying_more_than_is_owed_is_refused(self):
        with self.assertRaises(ValueError):
            self.pay("9000.00")
        self.assertEqual(Payment.objects.count(), 0)

    def test_a_zero_payment_is_refused(self):
        with self.assertRaises(ValueError):
            self.pay("0")

    def test_ageing_buckets_have_the_right_boundaries(self):
        for age, bucket in [(0, 0), (30, 0), (31, 1), (60, 1), (61, 2), (90, 2), (91, 3)]:
            self.assertEqual(bucket_index(age), bucket, age)

    def test_an_invoice_45_days_old_is_in_the_31_to_60_bucket(self):
        old = timezone.localdate() - timedelta(days=45)
        Invoice.objects.filter(pk=self.invoice.pk).update(invoice_date=old)
        rows, grand = ageing_report()
        self.assertEqual(rows[0]["customer"].name, "Retailer A")
        self.assertEqual(grand["buckets"][1], Decimal("7875.00"))
        self.assertEqual(grand["buckets"][0], Decimal("0.00"))
        self.assertEqual(grand["total"], Decimal("7875.00"))