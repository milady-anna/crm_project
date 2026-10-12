# orders/services.py
"""Вся бизнес-логика заказов - здесь. Админка (сейчас) и страницы (потом)
просто вызывают эти функции."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Substage, OrderItem, OrderItemComponent
from products.models import ProductComponent


@transaction.atomic
def create_substages_for_order(order):
    """
    Копирует подэтапы из типа заказа.
    Рассчитывает накопительный дедлайн: Дедлайн N = Дедлайн (N-1) + длительность N.
    """
    # Удаляем старые подэтапы, если они есть (для пересоздания)
    order.substages.all().delete()

    templates = order.order_type.ordertypetemplate_set.select_related(
        "template__default_stage"
    ).order_by("order_index")

    current_date = order.created_at.date()
    current_stage_id = None
    index_in_stage = 0

    for ott in templates:
        stage_id = (
            ott.template.default_stage_id
            if ott.template.default_stage
            else order.current_stage_id
        )

        # Сброс счетчика внутри этапа при смене этапа
        if stage_id != current_stage_id:
            current_stage_id = stage_id
            index_in_stage = 1
        else:
            index_in_stage += 1

        # Накопительный расчет дедлайна
        current_date = current_date + timezone.timedelta(days=ott.duration_days)

        Substage.objects.create(
            order=order,
            template=ott.template,  # Сохраняем связь для подтягивания документов!
            stage_id=stage_id,
            name=ott.template.name,  # Название строго из шаблона
            hint=ott.template.hint,  # Подсказка из шаблона
            duration_days=ott.duration_days,
            deadline=current_date,  # Расчетный дедлайн
            index_in_stage=index_in_stage,
            status="not_started",
        )

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
