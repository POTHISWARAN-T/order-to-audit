from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from masters.benchmark_helpers import item, make_benchmark_run, seed
from masters.models import Customer
from reports.builders import audit_log_report
from sales.models import Order, OrderLine

from .context import current_user
from .models import AuditLog


class AuditTrailTests(TestCase):
    def setUp(self):
        seed()
        call_command("setup_roles", stdout=StringIO())

    def test_creating_a_record_is_logged(self):
        Customer.objects.create(name="New Shop", state="Kerala")
        entry = AuditLog.objects.get(
            model_name="masters.Customer", action=AuditLog.CREATED, object_repr="New Shop"
        )
        self.assertIn("state=Kerala", entry.changes)

    def test_a_change_records_old_and_new_values_and_the_user(self):
        murukku = item("Murukku 200 g")
        admin = User.objects.get(username="factory_admin")
        token = current_user.set(admin)
        try:
            murukku.rate = Decimal("55.00")
            murukku.save()
        finally:
            current_user.reset(token)
        entry = AuditLog.objects.filter(
            model_name="masters.Item", action=AuditLog.CHANGED
        ).latest("pk")
        self.assertEqual(entry.changes, "rate: 50.00 -> 55.00")
        self.assertEqual(entry.user, admin)

    def test_saving_without_a_change_writes_nothing(self):
        murukku = item("Murukku 200 g")
        before = AuditLog.objects.count()
        murukku.save()
        self.assertEqual(AuditLog.objects.count(), before)

    def test_deleting_a_record_is_logged(self):
        customer = Customer.objects.create(name="Temp Shop", state="Kerala")
        customer.delete()
        self.assertTrue(
            AuditLog.objects.filter(
                model_name="masters.Customer", action=AuditLog.DELETED, object_repr="Temp Shop"
            ).exists()
        )

    def test_posting_a_production_run_is_logged(self):
        make_benchmark_run()
        entry = AuditLog.objects.get(
            model_name="production.ProductionRun", action=AuditLog.CHANGED
        )
        self.assertIn("posted: False -> True", entry.changes)


class AuditUserFromRequestTests(TestCase):
    def setUp(self):
        seed()
        call_command("setup_roles", stdout=StringIO())
        make_benchmark_run()
        murukku = item("Murukku 200 g")
        self.order = Order.objects.create(
            customer=Customer.objects.get(name="Retailer A"),
            salesman=User.objects.get(username="salesman_a"),
        )
        self.line = OrderLine.objects.create(
            order=self.order, product=murukku, quantity=150, rate=murukku.rate
        )
        self.client.login(username="factory_admin", password="Demo@12345")

    def review(self, action, qty, rate):
        return self.client.post(
            f"/manage/orders/{self.order.pk}/",
            {"action": action, f"qty_{self.line.pk}": qty, f"rate_{self.line.pk}": rate},
        )

    def test_an_approval_is_logged_against_the_logged_in_admin(self):
        self.review("approve", "150", "50.00")
        entry = AuditLog.objects.get(
            model_name="sales.Order", action=AuditLog.CHANGED, object_id=str(self.order.pk)
        )
        self.assertEqual(entry.changes, "status: SUBMITTED -> APPROVED")
        self.assertEqual(entry.user.username, "factory_admin")

    def test_an_edit_to_an_order_line_shows_old_and_new_values(self):
        self.review("save", "140", "52.00")
        entry = AuditLog.objects.get(model_name="sales.OrderLine", action=AuditLog.CHANGED)
        self.assertEqual(entry.changes, "quantity: 150 -> 140; rate: 50.00 -> 52.00")
        self.assertEqual(entry.user.username, "factory_admin")

    def test_the_audit_report_lists_the_change_with_the_user(self):
        self.review("approve", "150", "50.00")
        today = timezone.localdate()
        data = audit_log_report(today.replace(day=1), today)
        found = [r for r in data["rows"] if r[1] == "factory_admin" and r[3] == "sales.Order"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][6], "status: SUBMITTED -> APPROVED")