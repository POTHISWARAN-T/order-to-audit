from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

STOCK_ROLES = ("Admin", "Production", "Accountant", "Owner")


def role_required(*roles):
    """Allow a view only for users in one of these groups (or a superuser)."""

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or user.groups.filter(name__in=roles).exists():
                return view(request, *args, **kwargs)
            raise PermissionDenied

        return wrapper

    return decorator