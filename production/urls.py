from django.urls import path

from . import costing_views

urlpatterns = [
    path("costing/", costing_views.costing_home, name="costing_home"),
]