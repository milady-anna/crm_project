from django.db import models
from partners.models import Contractor  # <-- Импортируем таблицу Подрядчиков

class OurProduct(models.Model):
    """Наши товары (то, что мы продаем клиентам)"""
    name = models.CharField(max_length=200, verbose_name="Название товара")
    sale_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name="Цена продажи без НДС"
    )
    min_quantity = models.IntegerField(
        default=1, 
        verbose_name="Минимальный тираж (шт.)"
    )
    production_days = models.IntegerField(
        default=1, 
        verbose_name="Срок производства (дней)"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Наш товар"
        verbose_name_plural = "Наши товары"


class SupplierProduct(models.Model):
    """Товары и услуги поставщиков"""
    
    # ЗАМЕНИЛИ текстовое поле на ссылку (ForeignKey)
    contractor = models.ForeignKey(
        Contractor, 
        on_delete=models.PROTECT,# Запрещает удалять подрядчика, если у него есть товары
        null=True,    # <-- Всегда добавляйте при разработке
        blank=True,  
        verbose_name="Поставщик"
    )
    name = models.CharField(max_length=200, verbose_name="Название товара/услуги")
    product_type = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Тип (Одежда, Печать, Упаковка)"
    )
    color = models.CharField(max_length=50, blank=True, verbose_name="Цвет")
    size = models.CharField(max_length=50, blank=True, verbose_name="Размер")
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name="Цена закупки без НДС"
    )
    lead_time_days = models.IntegerField(
        default=1, 
        verbose_name="Срок поставки (дней)"
    )

    def __str__(self):
        return f"{self.name} ({self.contractor})"

    class Meta:
        verbose_name = "Товар поставщика"
        verbose_name_plural = "Товары поставщиков"

class ProductComponent(models.Model):
    """Состав нашего товара (спецификация) - из чего состоит и на каком этапе оплачивается"""
    our_product = models.ForeignKey(
        OurProduct, 
        on_delete=models.CASCADE, 
        related_name='components',
        verbose_name="Наш товар"
    )
    supplier_product = models.ForeignKey(
        SupplierProduct, 
        on_delete=models.PROTECT,
        verbose_name="Товар/услуга поставщика"
    )
    quantity = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=1,
        verbose_name="Количество на 1 шт. нашего товара"
    )
    substage_template = models.ForeignKey(
        'orders.SubstageTemplate', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Шаблон подэтапа (когда оплачивать)"
    )
    
    def __str__(self):
        return f"{self.supplier_product.name} для {self.our_product.name}"
    
    class Meta:
        verbose_name = "Компонент товара"
        verbose_name_plural = "Компоненты товаров"