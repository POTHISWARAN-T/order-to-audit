from django.urls import path

from . import dashboard_views, views

urlpatterns = [
    path("dashboard/", dashboard_views.dashboard, name="dashboard"),
    path("reports/", views.report_index, name="report_index"),
    path("reports/<slug:slug>/", views.report_view, name="report_view"),
]