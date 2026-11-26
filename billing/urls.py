from django.urls import path

from . import credit_views, payment_views, views

urlpatterns = [
    path("manage/billing/", views.billing_home, name="billing_home"),
    path("manage/orders/<int:order_pk>/invoice/", views.invoice_create, name="invoice_create"),
    path("manage/invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("manage/invoices/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("manage/invoices/<int:pk>/dispatch/", views.invoice_dispatch, name="invoice_dispatch"),
    path("manage/payments/", payment_views.payments_home, name="payments_home"),
    path("manage/credit-notes/", credit_views.credit_notes_home, name="credit_notes_home"),
    path("manage/invoices/<int:pk>/cancel/", credit_views.credit_note_create, name="credit_note_create"),
]