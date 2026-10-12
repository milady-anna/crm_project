# dashboard/urls.py
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="order_list"),
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
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
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
]
