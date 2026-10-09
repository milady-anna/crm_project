# products/models.py
from decimal import Decimal

from django.db import models
from partners.models import Contractor

# Модели из orders здесь НЕ импортируем (получится циклический импорт).
# Ссылаемся на них строкой: 'orders.SubstageTemplate'.


class OurProduct(models.Model):
    """Наши товары (то, что мы продаём клиентам)"""
    name = models.CharField(max_length=200, verbose_name="Название товара")
    sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Базовая цена продажи без НДС (справочно)",
    )
    min_quantity = models.PositiveIntegerField(default=1, verbose_name="Минимальный тираж (шт.)")
    production_days = models.PositiveIntegerField(default=1, verbose_name="Срок производства (дней)")

    def __str__(self):
        return self.name

    @property
    def min_cost(self):
        """Себестоимость 1 шт. по спецификации (только для показа, в базе не хранится)."""
        if not self.pk:
            return Decimal("0")
        components = self.components.select_related("supplier_product")
        return sum((c.quantity * c.supplier_product.unit_price for c in components), Decimal("0"))

    class Meta:
        verbose_name = "Наш товар"
        verbose_name_plural = "Наши товары"


class SupplierProduct(models.Model):
    """Товары и услуги поставщиков"""
    contractor = models.ForeignKey(
        Contractor, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Поставщик"
    )
    name = models.CharField(max_length=200, verbose_name="Название товара/услуги")
    product_type = models.CharField(max_length=100, blank=True, verbose_name="Тип (Одежда, Печать, Упаковка)")
    color = models.CharField(max_length=50, blank=True, verbose_name="Цвет")
    size = models.CharField(max_length=50, blank=True, verbose_name="Размер")
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Цена закупки без НДС"
    )
    lead_time_days = models.PositiveIntegerField(default=1, verbose_name="Срок поставки (дней)")

    def __str__(self):
        return f"{self.name} ({self.contractor})"

    class Meta:
        verbose_name = "Товар поставщика"
        verbose_name_plural = "Товары поставщиков"


class ProductComponent(models.Model):
    """Состав нашего товара (спецификация). При создании позиции заказа копируется в заказ."""
    our_product = models.ForeignKey(
        OurProduct, on_delete=models.CASCADE, related_name="components", verbose_name="Наш товар"
    )
    supplier_product = models.ForeignKey(
        SupplierProduct, on_delete=models.PROTECT, verbose_name="Товар/услуга поставщика"
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1,
        verbose_name="Количество на 1 шт. нашего товара",
    )
    substage_template = models.ForeignKey(
        "orders.SubstageTemplate", on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Шаблон подэтапа (когда оплачивать)",
    )

    def __str__(self):
        return f"{self.supplier_product.name} для {self.our_product.name}"

    class Meta:
        verbose_name = "Компонент товара"
        verbose_name_plural = "Компоненты товаров"
