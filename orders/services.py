from django.utils import timezone
from .models import Substage

def create_substages_for_order(order):
    """Создает подэтапы для заказа на основе OrderTypeTemplate"""
    templates = order.order_type.templates.select_related('template__default_stage').order_by('ordertypetemplate__order_index')
    
    current_date = timezone.now().date()
    
    for ott in templates:
        Substage.objects.create(
            order=order,
            template=ott.template,
            stage=ott.template.default_stage,
            name=ott.template.name,
            duration_days=ott.duration_days,
            deadline=current_date, # Упрощено для MVP: дедлайн = сегодня + логика может быть добавлена позже
            order_index=ott.order_index,
            status='not_started'
        )
    
    order.update_current_stage()