# dashboard/urls.py
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard:order_list"), name="home"),
    path("orders/", views.OrderListView.as_view(), name="order_list"),
]
