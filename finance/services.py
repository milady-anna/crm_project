# finance/services.py
from django.db import transaction

from .models import BudgetItem


@transaction.atomic
def build_budget_for_order_item(order_item):
    """Создаёт плановые платежи по компонентам позиции заказа (снимку спецификации).
    Повторный вызов безопасен: существующий платёж не дублируется, а получает
    новую сумму. Дату и подрядчика, которые менеджер мог поправить, не трогаем."""
    order = order_item.order
    components = order_item.components.select_related("supplier_product__contractor", "substage_template")

    for comp in components:
        substage = None
        if comp.substage_template_id:
            substage = (
                order.substages.filter(template_id=comp.substage_template_id)
                .order_by("stage__order_index", "index_in_stage", "id")
                .first()
            )

        amount = round(order_item.quantity * comp.quantity * comp.unit_price, 2)

        budget_item, created = BudgetItem.objects.get_or_create(
            order_item=order_item,
            item_component=comp,
            defaults={
                "order": order,
                "substage": substage,
                "component_name": comp.supplier_product.name,
                "contractor": comp.supplier_product.contractor,
                "flow_type": "expense",
                "amount_plan": amount,
                "date_plan": substage.deadline if substage else None,
            },
        )
        if created:
            continue

        changed = []
        if budget_item.amount_plan != amount:
            budget_item.amount_plan = amount
            changed.append("amount_plan")
        if budget_item.substage_id is None and substage:  # подэтап появился позже
            budget_item.substage = substage
            changed.append("substage")
            if budget_item.date_plan is None:
                budget_item.date_plan = substage.deadline
                changed.append("date_plan")
        if changed:
            budget_item.save(update_fields=changed)


def build_budget_for_order(order):
    """Строит бюджет для всех позиций заказа."""
    for item in order.items.all():
        build_budget_for_order_item(item)
