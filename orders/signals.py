from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OrderItem
from products.models import ProductComponent
from finance.models import BudgetItem


@receiver(post_save, sender=OrderItem)
def create_budget_items_on_order_item_save(sender, instance, created, **kwargs):
    """Автоматически создаем плановые платежи при добавлении товара в заказ"""
    if not created:
        return  # Только при создании новой позиции
    
    # Получаем состав товара
    components = ProductComponent.objects.filter(our_product=instance.product)
    
    for component in components:
        # Считаем сумму: количество в заказе × количество в компоненте × цена поставщика
        amount = instance.quantity * component.quantity * component.supplier_product.unit_price
        
        # Находим или создаем подэтап
        substage = None
        if component.substage_template:
            # Ищем подэтап этого заказа, соответствующий шаблону
            substage = instance.order.substages.filter(
                template=component.substage_template
            ).first()
        
        # Создаем плановый платеж
        BudgetItem.objects.create(
            order=instance.order,
            order_item=instance,
            substage=substage,
            component_name=component.supplier_product.name,
            contractor=None,  # Менеджер выберет вручную
            flow_type='expense',
            amount_plan=amount,
            date_plan=substage.deadline if substage else None,
            status='planned'
        )