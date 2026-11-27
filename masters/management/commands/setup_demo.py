from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from masters.management.commands.setup_roles import DEMO_PASSWORD


class Command(BaseCommand):
    help = "One command for a working demo: tables, benchmark master data, roles and logins"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-migrate", action="store_true", help="Do not create or update the tables"
        )

    def handle(self, *args, **options):
        if not options["skip_migrate"]:
            call_command("migrate", interactive=False, verbosity=0)
        call_command("load_seed", stdout=self.stdout)
        call_command("setup_roles", stdout=self.stdout)
        if not User.objects.filter(username="demo_admin").exists():
            User.objects.create_superuser("demo_admin", password=DEMO_PASSWORD)
        self.stdout.write(self.style.SUCCESS("Demo ready. Log in at /accounts/login/"))
        self.stdout.write(f"Every demo user has the password {DEMO_PASSWORD}")