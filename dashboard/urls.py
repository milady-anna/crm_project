# dashboard/urls.py
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "dashboard"

urlpatterns = [
    path("orders/", views.OrderListView.as_view(), name="order_list"),
    path("orders/create/", views.OrderCreateView.as_view(), name="order_create"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("clients/", views.ClientListView.as_view(), name="client_list"),
    path("clients/<int:pk>/", views.ClientDetailView.as_view(), name="client_detail"),
    path("contractors/", views.ContractorListView.as_view(), name="contractor_list"),
    path(
        "contractors/<int:pk>/",
        views.ContractorDetailView.as_view(),
        name="contractor_detail",
    ),
    path(
        "contractors/<int:pk>/review/",
        views.AddContractorReviewView.as_view(),
        name="add_contractor_review",
    ),
    path(
        "orders/<int:pk>/substage/<int:substage_pk>/status/",
        views.UpdateSubstageStatusView.as_view(),
        name="update_substage_status",
    ),
    path(
        "orders/<int:pk>/comment/", views.AddCommentView.as_view(), name="add_comment"
    ),
    path(
        "orders/<int:pk>/budget/",
        views.AddBudgetItemView.as_view(),
        name="add_budget_item",
    ),
    path(
        "order-items/<int:pk>/update/",
        views.UpdateOrderItemView.as_view(),
        name="update_order_item",
    ),
    path(
        "orders/<int:pk>/items/add/",
        views.AddOrderItemView.as_view(),
        name="add_order_item",
    ),
    path(
        "order-items/<int:pk>/delete/",
        views.DeleteOrderItemView.as_view(),
        name="delete_order_item",
    ),
    path(
        "orders/<int:pk>/documents/",
        views.UpdateOrderDocumentsView.as_view(),
        name="update_order_documents",
    ),
    path(
        "budget-items/<int:pk>/update/",
        views.UpdateBudgetItemView.as_view(),
        name="update_budget_item",
    ),
    path(
        "orders/<int:pk>/transactions/add/",
        views.AddTransactionView.as_view(),
        name="add_transaction",
    ),
    path(
        "transactions/<int:pk>/delete/",
        views.DeleteTransactionView.as_view(),
        name="delete_transaction",
    ),
    path("orders/create/", views.OrderCreateView.as_view(), name="order_create"),
    path(
        "contractors/<int:pk>/update-comment/",
        views.UpdateContractorCommentView.as_view(),
        name="update_contractor_comment",
    ),
]
