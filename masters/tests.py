from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from inventory.services import get_balance
from masters.models import Item


class SetupDemoTests(TestCase):
    def run_setup(self):
        call_command("setup_demo", skip_migrate=True, stdout=StringIO())

    def test_one_command_gives_a_working_demo(self):
        self.run_setup()
        names = ("demo_admin", "salesman_a", "salesman_b", "factory_admin",
                 "production_sup", "accountant", "owner")
        for username in names:
            self.assertTrue(User.objects.filter(username=username).exists(), username)
        self.assertTrue(User.objects.get(username="demo_admin").is_superuser)
        self.assertEqual(get_balance(Item.objects.get(name="Murukku 200 g")), 50)

    def test_running_it_twice_changes_nothing(self):
        self.run_setup()
        users = User.objects.count()
        self.run_setup()
        self.assertEqual(User.objects.count(), users)
        self.assertEqual(get_balance(Item.objects.get(name="Murukku 200 g")), 50)