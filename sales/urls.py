from django.urls import path

from . import manage_views, views

urlpatterns = [
    path("orders/new/", views.new_order, name="new_order"),
    path("orders/", views.my_orders, name="my_orders"),
    path("manage/orders/", manage_views.order_list, name="order_list"),
    path("manage/orders/<int:pk>/", manage_views.order_review, name="order_review"),
]