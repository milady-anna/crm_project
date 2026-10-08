from django.db import models
from orders.models import Order, Substage, OrderItem
from partners.models import Contractor


class BudgetItem(models.Model):
    """Плановый платеж (статья бюджета)"""
    STATUS_CHOICES = [
        ('planned', 'Запланирован'),
        ('paid', 'Оплачен'),
    ]
    
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='budget_items',
        verbose_name="Заказ"
    )
    order_item = models.ForeignKey(
        OrderItem, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='budget_items',
        verbose_name="Позиция товара (для группировки)"
    )
    substage = models.ForeignKey(
        Substage, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Подэтап"
    )
    component_name = models.CharField(
        max_length=200, 
        verbose_name="Название компонента"
    )
    contractor = models.ForeignKey(
        Contractor, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Подрядчик"
    )
    flow_type = models.CharField(
        max_length=10,
        choices=[('income', 'Приход'), ('expense', 'Расход')],
        default='expense',
        verbose_name="Тип"
    )
    amount_plan = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name="Плановая сумма"
    )
    date_plan = models.DateField(
        null=True,
        blank=True,
        verbose_name="Плановая дата"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='planned',
        verbose_name="Статус"
    )
    
    def __str__(self):
        return f"{self.component_name} ({self.amount_plan} руб.)"
    
    class Meta:
        verbose_name = "Плановый платеж"
        verbose_name_plural = "Плановые платежи"
        ordering = ['order_item', 'date_plan']


class Transaction(models.Model):
    """Фактический платеж"""
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
    ]
    
    budget_item = models.ForeignKey(
        BudgetItem, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name="Плановый платеж"
    )
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name="Заказ"
    )
    flow_type = models.CharField(
        max_length=10,
        choices=[('income', 'Приход'), ('expense', 'Расход')],
        default='expense',
        verbose_name="Тип"
    )
    amount_fact = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name="Фактическая сумма"
    )
    date_fact = models.DateField(
        null=True,
        blank=True,
        verbose_name="Фактическая дата"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=[('cashless', 'Безнал'), ('cash', 'Наличные'), ('card', 'Карта')],
        default='cashless',
        verbose_name="Способ оплаты"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий"
    )
    
    def save(self, *args, **kwargs):
        # Автоматически ставим дату при оплате
        if self.status == 'paid' and not self.date_fact:
            from django.utils import timezone
            self.date_fact = timezone.now().date()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.amount_fact} руб. ({self.get_status_display()})"
    
    class Meta:
        verbose_name = "Фактический платеж"
        verbose_name_plural = "Фактические платежи"
        ordering = ['-date_fact']


class Document(models.Model):
    """Документы (счета, акты, платежки)"""
    DOC_TYPE_CHOICES = [
        ('invoice', 'Счет на оплату'),
        ('act', 'Акт выполненных работ'),
        ('payment_order', 'Платежное поручение'),
        ('contract', 'Договор'),
        ('waybill', 'Накладная'),
    ]
    
    transaction = models.ForeignKey(
        Transaction, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents',
        verbose_name="Платеж"
    )
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents',
        verbose_name="Заказ"
    )
    doc_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        verbose_name="Тип документа"
    )
    number = models.CharField(
        max_length=100,
        verbose_name="Номер документа"
    )
    date = models.DateField(
        verbose_name="Дата документа"
    )
    file = models.FileField(
        upload_to='documents/%Y/%m/',
        blank=True,
        verbose_name="Файл"
    )
    
    def __str__(self):
        return f"{self.get_doc_type_display()} №{self.number}"
    
    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ['-date']