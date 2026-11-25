from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from django.db import transaction

DEMO_PASSWORD = "Demo@12345"  # demo logins only


def codes(app, models, actions):
    """Build (app, codename) pairs such as ('masters', 'view_item')."""
    return [
        (app, f"{action}_{model}")
        for model in models.split()
        for action in actions.split()
    ]


VIEW_ALL = (
    codes("masters", "item customer supplier bom bomline", "view")
    + codes("inventory", "stockmovement purchase", "view")
    + codes("production", "productionrun productionrunline", "view")
)

ROLES = {
    "Salesman": [],
    "Admin": (
        codes("masters", "item customer supplier bom bomline", "add change view")
        + codes("inventory", "stockmovement purchase", "view")
        + codes("production", "productionrun productionrunline", "view")
    ),
    "Production": (
        codes("masters", "item supplier bom bomline", "view")
        + codes("inventory", "stockmovement", "view")
        + codes("inventory", "purchase", "add view")
        + codes("production", "productionrun productionrunline", "add view")
    ),
    "Accountant": VIEW_ALL,
    "Owner": VIEW_ALL,
}

# (username, role, can use the admin site)
USERS = [
    ("salesman_a", "Salesman", False),
    ("salesman_b", "Salesman", False),
    ("factory_admin", "Admin", True),
    ("production_sup", "Production", True),
    ("accountant", "Accountant", True),
    ("owner", "Owner", True),
]


class Command(BaseCommand):
    help = "Create the role groups and demo users"

    @transaction.atomic
    def handle(self, *args, **options):
        for role, wanted in ROLES.items():
            group, _ = Group.objects.get_or_create(name=role)
            permissions = [
                Permission.objects.get(content_type__app_label=app, codename=codename)
                for app, codename in wanted
            ]
            group.permissions.set(permissions)

        for username, role, is_staff in USERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(DEMO_PASSWORD)
            user.is_staff = is_staff
            user.save()
            user.groups.set([Group.objects.get(name=role)])

        self.stdout.write(self.style.SUCCESS("Roles and demo users ready."))
        self.stdout.write(f"Demo password for every user: {DEMO_PASSWORD}")