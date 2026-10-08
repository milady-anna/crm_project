# dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('orders/', views.OrderListView.as_view(), name='order_list'),
]