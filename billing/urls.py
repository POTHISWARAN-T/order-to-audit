from django.urls import path

from . import views

urlpatterns = [
    path("manage/billing/", views.billing_home, name="billing_home"),
    path("manage/orders/<int:order_pk>/invoice/", views.invoice_create, name="invoice_create"),
    path("manage/invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("manage/invoices/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("manage/invoices/<int:pk>/dispatch/", views.invoice_dispatch, name="invoice_dispatch"),
]