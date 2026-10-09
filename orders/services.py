# orders/services.py
"""Вся бизнес-логика заказов - здесь. Админка (сейчас) и страницы (потом)
просто вызывают эти функции."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Substage


@transaction.atomic
def create_substages_for_order(order):
    """Копирует в заказ подэтапы из его типа. Если подэтапы уже есть - ничего не делает."""
    if order.substages.exists():
        return

    rows = order.order_type.ordertypetemplate_set.select_related(
        "template__default_stage"
    ).order_by("template__default_stage__order_index", "order_index", "id")

    deadline = timezone.localdate()
    counters = {}  # номер подэтапа внутри этапа
    new_substages = []
    for row in rows:
        template = row.template
        stage_id = template.default_stage_id
        counters[stage_id] = counters.get(stage_id, 0) + 1
        deadline += timedelta(days=row.duration_days)  # дедлайны идут друг за другом
        new_substages.append(Substage(
            order=order,
            template=template,
            stage_id=stage_id,
            name=template.name,
            hint=template.hint,
            duration_days=row.duration_days,
            deadline=deadline,
            index_in_stage=counters[stage_id],
        ))
    Substage.objects.bulk_create(new_substages)
    order.update_current_stage()


@transaction.atomic
def sync_order(order, created=False):
    """Единая точка сборки заказа. Порядок важен:
    1) подэтапы (только для нового заказа), 2) цены позиций,
    3) бюджет (ему нужны подэтапы), 4) этап заказа."""
    from finance.services import build_budget_for_order

    if created:
        create_substages_for_order(order)
    for item in order.items.all():
        item.refresh_prices()
    build_budget_for_order(order)
    order.update_current_stage()
