from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .permissions import STOCK_ROLES


@login_required
def home(request):
    user = request.user
    roles = list(user.groups.values_list("name", flat=True))
    if user.is_superuser:
        roles.append("Superuser")
    can_stock = user.is_superuser or bool(set(roles) & set(STOCK_ROLES))
    return render(request, "masters/home.html", {"roles": roles, "can_stock": can_stock})