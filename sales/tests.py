from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from masters.benchmark_helpers import item, make_benchmark_run, seed
from masters.models import Customer

from .models import Order, OrderLine
from .services import available_stock, stock_rows


def make_order(user, customer_name, qty, status=Order.SUBMITTED):
    murukku = item("Murukku 200 g")
    order = Order.objects.create(
        customer=Customer.objects.get(name=customer_name), salesman=user, status=status
    )
    OrderLine.objects.create(order=order, product=murukku, quantity=qty, rate=murukku.rate)
    return order


class StockCheckTests(TestCase):
    def setUp(self):
        seed()
        make_benchmark_run()
        self.user = User.objects.create_user("tester", password="x")
        self.murukku = item("Murukku 200 g")

    def test_stock_covers_the_first_order(self):
        order_a = make_order(self.user, "Retailer A", 150)
        row = stock_rows(order_a)[0]
        self.assertEqual(row["available"], Decimal("238"))
        self.assertEqual(row["shortage"], Decimal("0"))

    def test_order_total_is_quantity_times_rate(self):
        self.assertEqual(make_order(self.user, "Retailer A", 150).total, Decimal("7500.00"))

    def test_second_order_is_32_packets_short_once_the_first_is_approved(self):
        make_order(self.user, "Retailer A", 150, status=Order.APPROVED)
        order_b = make_order(self.user, "Distributor B", 120)
        row = stock_rows(order_b)[0]
        self.assertEqual(row["available"], Decimal("88"))
        self.assertEqual(row["shortage"], Decimal("32"))

    def test_submitted_orders_do_not_claim_stock(self):
        make_order(self.user, "Retailer A", 150)
        order_b = make_order(self.user, "Distributor B", 120)
        self.assertEqual(available_stock(self.murukku, exclude_order=order_b), Decimal("238"))


class AccessAndOrderFlowTests(TestCase):
    def setUp(self):
        seed()
        call_command("setup_roles", stdout=StringIO())
        make_benchmark_run()
        self.murukku = item("Murukku 200 g")

    def test_salesman_places_an_order(self):
        retailer = Customer.objects.get(name="Retailer A")
        self.client.login(username="salesman_a", password="Demo@12345")
        response = self.client.post(
            "/orders/new/", {"customer": retailer.pk, f"qty_{self.murukku.pk}": "150"}
        )
        self.assertRedirects(response, "/orders/")
        order = Order.objects.get()
        line = order.lines.get()
        self.assertEqual(order.salesman.username, "salesman_a")
        self.assertEqual(order.status, Order.SUBMITTED)
        self.assertEqual(line.quantity, 150)
        self.assertEqual(line.rate, Decimal("50.00"))

    def test_an_order_without_any_quantity_is_refused(self):
        retailer = Customer.objects.get(name="Retailer A")
        self.client.login(username="salesman_a", password="Demo@12345")
        response = self.client.post("/orders/new/", {"customer": retailer.pk})
        self.assertContains(response, "at least one product")
        self.assertEqual(Order.objects.count(), 0)

    def test_a_salesman_sees_only_his_own_orders(self):
        order = make_order(User.objects.get(username="salesman_a"), "Retailer A", 10)
        self.client.login(username="salesman_b", password="Demo@12345")
        response = self.client.get("/orders/")
        self.assertNotContains(response, f"ORD-{order.pk}")

    def test_a_salesman_cannot_open_stock_or_admin_pages(self):
        self.client.login(username="salesman_a", password="Demo@12345")
        self.assertEqual(self.client.get("/stock/").status_code, 403)
        self.assertEqual(self.client.get("/manage/orders/").status_code, 403)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_a_visitor_who_is_not_logged_in_is_sent_to_the_login_page(self):
        response = self.client.get("/stock/")
        self.assertRedirects(
            response, "/accounts/login/?next=/stock/", fetch_redirect_response=False
        )

    def test_admin_can_open_the_order_screens(self):
        order = make_order(User.objects.get(username="salesman_a"), "Retailer A", 150)
        self.client.login(username="factory_admin", password="Demo@12345")
        self.assertEqual(self.client.get("/manage/orders/").status_code, 200)
        self.assertEqual(self.client.get(f"/manage/orders/{order.pk}/").status_code, 200)

    def test_admin_can_approve_an_order_that_stock_covers(self):
        order = make_order(User.objects.get(username="salesman_a"), "Retailer A", 150)
        line = order.lines.get()
        self.client.login(username="factory_admin", password="Demo@12345")
        response = self.client.post(
            f"/manage/orders/{order.pk}/",
            {"action": "approve", f"qty_{line.pk}": "150", f"rate_{line.pk}": "50.00"},
        )
        self.assertRedirects(response, "/manage/orders/", fetch_redirect_response=False)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.APPROVED)

    def test_admin_cannot_approve_an_order_when_stock_is_short(self):
        seller = User.objects.get(username="salesman_a")
        make_order(seller, "Retailer A", 150, status=Order.APPROVED)
        order_b = make_order(seller, "Distributor B", 120)
        line = order_b.lines.get()
        self.client.login(username="factory_admin", password="Demo@12345")
        response = self.client.post(
            f"/manage/orders/{order_b.pk}/",
            {"action": "approve", f"qty_{line.pk}": "120", f"rate_{line.pk}": "50.00"},
        )
        self.assertContains(response, "Cannot approve")
        order_b.refresh_from_db()
        self.assertEqual(order_b.status, Order.SUBMITTED)