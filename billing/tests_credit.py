from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from inventory.models import StockMovement
from inventory.services import get_balance
from masters.benchmark_helpers import item, make_benchmark_run, seed
from masters.models import Customer
from reports.builders import credit_notes_register
from sales.models import Order, OrderLine

from .credit import issue_credit_note
from .models import Invoice, Payment
from .receivables import ageing_report, outstanding, record_payment
from .services import create_invoice, dispatch_invoice


class CreditNoteTests(TestCase):
    def setUp(self):
        seed()
        make_benchmark_run()
        self.user = User.objects.create_user("biller", password="x")
        self.murukku = item("Murukku 200 g")
        self.invoice = self.new_invoice(150)

    def new_invoice(self, qty):
        order = Order.objects.create(
            customer=Customer.objects.get(name="Retailer A"),
            salesman=self.user,
            status=Order.APPROVED,
        )
        OrderLine.objects.create(
            order=order, product=self.murukku, quantity=qty, rate=self.murukku.rate
        )
        return create_invoice(order, self.user)

    def test_a_credit_note_cancels_the_invoice_and_clears_the_balance(self):
        note = issue_credit_note(self.invoice, "Wrong order", False, self.user)
        self.assertTrue(note.credit_note_number.startswith("CN/"))
        self.assertTrue(note.credit_note_number.endswith("/0001"))
        self.assertEqual(note.total_amount, Decimal("7875.00"))
        self.assertEqual(outstanding(self.invoice), Decimal("0.00"))
        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())
        self.invoice.order.refresh_from_db()
        self.assertEqual(self.invoice.order.status, Order.CANCELLED)

    def test_credit_note_numbers_run_in_sequence(self):
        second = self.new_invoice(10)
        first_note = issue_credit_note(self.invoice, "Wrong order", False, self.user)
        second_note = issue_credit_note(second, "Duplicate", False, self.user)
        self.assertTrue(first_note.credit_note_number.endswith("/0001"))
        self.assertTrue(second_note.credit_note_number.endswith("/0002"))

    def test_returned_goods_go_back_into_stock_through_the_ledger(self):
        dispatch_invoice(self.invoice, self.user)
        self.assertEqual(get_balance(self.murukku), Decimal("88"))
        note = issue_credit_note(self.invoice, "Goods rejected", True, self.user)
        self.assertEqual(get_balance(self.murukku), Decimal("238"))
        movement = StockMovement.objects.get(source_ref=note.credit_note_number)
        self.assertEqual(movement.quantity, Decimal("150"))

    def test_goods_cannot_be_returned_before_they_were_dispatched(self):
        with self.assertRaises(ValueError):
            issue_credit_note(self.invoice, "Goods rejected", True, self.user)
        self.assertEqual(get_balance(self.murukku), Decimal("238"))

    def test_a_reason_is_required(self):
        with self.assertRaises(ValueError):
            issue_credit_note(self.invoice, "   ", False, self.user)

    def test_an_invoice_cannot_be_cancelled_twice(self):
        issue_credit_note(self.invoice, "Wrong order", False, self.user)
        with self.assertRaises(ValueError):
            issue_credit_note(self.invoice, "Again", False, self.user)

    def test_no_payment_can_be_taken_after_cancellation(self):
        issue_credit_note(self.invoice, "Wrong order", False, self.user)
        with self.assertRaises(ValueError):
            record_payment(
                self.invoice, Decimal("100"), date.today(), Payment.CASH, "", self.user
            )

    def test_money_already_paid_becomes_a_refund_due(self):
        record_payment(self.invoice, Decimal("4000"), date.today(), Payment.CASH, "", self.user)
        issue_credit_note(self.invoice, "Wrong order", False, self.user)
        self.assertEqual(outstanding(self.invoice), Decimal("-4000.00"))

    def test_a_cancelled_invoice_is_not_in_the_ageing_report(self):
        issue_credit_note(self.invoice, "Wrong order", False, self.user)
        rows, grand = ageing_report()
        self.assertEqual(rows, [])
        self.assertEqual(grand["total"], Decimal("0.00"))

    def test_the_credit_notes_register_lists_the_note(self):
        issue_credit_note(self.invoice, "Wrong order", False, self.user)
        today = timezone.localdate()
        data = credit_notes_register(today.replace(day=1), today)
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["totals"][11], Decimal("7875.00"))