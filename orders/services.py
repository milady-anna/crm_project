# orders/services.py
from django.utils import timezone
from .models import Substage

def create_substages_for_order(order):
    """Создает подэтапы для заказа на основе OrderTypeTemplate с нумерацией внутри этапа"""
    templates = order.order_type.ordertypetemplate_set.select_related(
        'template__default_stage'
    ).order_by('template__default_stage__order_index', 'order_index')
    
    current_date = timezone.now().date()
    current_stage_id = None
    index_in_stage = 0
    
    for ott in templates:
        stage_id = ott.template.default_stage_id if ott.template.default_stage else None
        
        # Если этап изменился, сбрасываем счетчик
        if stage_id != current_stage_id:
            current_stage_id = stage_id
            index_in_stage = 1
        else:
            index_in_stage += 1
        
        Substage.objects.create(
            order=order,
            template=ott.template,
            stage_id=stage_id,
            name=ott.template.name,
            duration_days=ott.duration_days,
            deadline=current_date,
            index_in_stage=index_in_stage,
            status='not_started'
        )
    
    order.update_current_stage()