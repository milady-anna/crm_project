# dashboard/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.utils import timezone
from django.views.generic import ListView

from orders.models import Order, Stage


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "dashboard/order_list.html"
    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        # select_related / prefetch_related: все связанные данные одним заходом, без лишних запросов
        queryset = (
            Order.objects
            .select_related("client", "manager", "current_stage", "order_type")
            .prefetch_related("items")
            .order_by("deadline_plan")
        )

        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(number__icontains=search_query) | Q(client__name__icontains=search_query)
            )

        stage_id = self.request.GET.get("stage", "")
        if stage_id.isdigit():
            queryset = queryset.filter(current_stage_id=stage_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = timezone.localdate()
        context["stages"] = Stage.objects.all()
        return context
