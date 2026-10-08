from django.db import transaction
from .models import BudgetItem
from products.models import ProductComponent

@transaction.atomic
def build_budget_for_order_item(order_item):
    """Создает или ОБНОВЛЯЕТ плановые платежи. Работает корректно при изменении количества."""
    order = order_item.order
    components = ProductComponent.objects.filter(our_product=order_item.product).select_related('supplier_product__contractor', 'substage_template')
    
    for comp in components:
        substage = order.substages.filter(template=comp.substage_template).order_by('order_index').first()
        amount = order_item.quantity * comp.quantity * comp.supplier_product.unit_price
        
        # Используем update_or_create, чтобы обновлять сумму при изменении количества в OrderItem
        BudgetItem.objects.update_or_create(
            order_item=order_item,
            source_component=comp,
            defaults={
                'order': order,
                'substage': substage,
                'component_name': comp.supplier_product.name,
                'contractor': comp.supplier_product.contractor,
                'flow_type': 'expense',
                'amount_plan': amount,
                'date_plan': substage.deadline if substage else None,
            }
        )