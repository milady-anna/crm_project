# dashboard/views.py
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from orders.models import Order
from django.utils import timezone

class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'dashboard/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20  # По 20 заказов на страницу

    def get_queryset(self):
        # Берем заказы с связанными данными за 1 запрос (оптимизация)
        queryset = Order.objects.select_related('client', 'manager', 'current_stage', 'order_type').order_by('deadline_plan')
        
        # Поиск по номеру или клиенту
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(number__icontains=search_query) | 
                Q(client__short_name__icontains=search_query) |
                Q(client__full_name__icontains=search_query)
            )
        
        # Фильтр по этапу
        stage_id = self.request.GET.get('stage', '')
        if stage_id:
            queryset = queryset.filter(current_stage_id=stage_id)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        # Для фильтра в шаблоне
        from orders.models import Stage
        context['stages'] = Stage.objects.all()
        return context