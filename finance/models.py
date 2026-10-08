# finance/models.py
from django.db import models
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from orders.models import Order, Substage, OrderItem
from partners.models import Contractor
from core.models import TimeStampedModel # <-- Импортируем наши даты


class BudgetItem(models.Model):
    """Плановый платеж (статья бюджета)"""
    FLOW_CHOICES = [('income', 'Приход'), ('expense', 'Расход')]
    
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='budget_items', verbose_name="Заказ")
    order_item = models.ForeignKey(
        'orders.OrderItem', 
        on_delete=models.CASCADE, # <-- ИЗМЕНЕНО с PROTECT на CASCADE, чтобы можно было править заказ
        null=True, 
        blank=True, 
        related_name='budget_items', 
        verbose_name="Позиция товара"
    )
    
    # НОВОЕ ПОЛЕ для связи с компонентом (чтобы сервис не создавал дубликаты)
    source_component = models.ForeignKey('products.ProductComponent', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Источник (компонент)")
    
    substage = models.ForeignKey(Substage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Подэтап")
    component_name = models.CharField(max_length=200, verbose_name="Название компонента")
    contractor = models.ForeignKey(Contractor, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Подрядчик")
    
    flow_type = models.CharField(max_length=10, choices=FLOW_CHOICES, default='expense', verbose_name="Тип")
    amount_plan = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Плановая сумма")
    date_plan = models.DateField(null=True, blank=True, verbose_name="Плановая дата")
    
    # МЫ УБРАЛИ ПОЛЕ status отсюда! Теперь оно вычисляется автоматически.

    @property
    def payment_state(self):
        """Автоматически считает, сколько оплачено, на основе реальных транзакций"""
        paid_amount = self.transactions.filter(status='paid').aggregate(
            total=Coalesce(Sum('amount_fact'), Value(0))
        )['total']
        
        if paid_amount == 0:
            return "Не оплачено"
        elif paid_amount >= self.amount_plan:
            return "Оплачено"
        else:
            return f"Частично ({paid_amount} из {self.amount_plan})"

    def __str__(self):
        return f"{self.component_name} ({self.amount_plan} руб.)"
    
    class Meta:
        verbose_name = "Плановый платеж"
        verbose_name_plural = "Плановые платежи"
        ordering = ['order_item', 'date_plan']


class Transaction(TimeStampedModel): # <-- НАСЛЕДУЕМСЯ ОТ TimeStampedModel
    """Фактический платеж"""
    STATUS_CHOICES = [('pending', 'Ожидает оплаты'), ('paid', 'Оплачен')]
    METHOD_CHOICES = [('cashless', 'Безнал'), ('cash', 'Наличные'), ('card', 'Карта')]
    
    budget_item = models.ForeignKey(BudgetItem, on_delete=models.PROTECT, null=True, blank=True, related_name='transactions', verbose_name="Плановый платеж")
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='transactions', verbose_name="Заказ") # <-- PROTECT: нельзя удалить заказ с платежами
    
    flow_type = models.CharField(max_length=10, choices=[('income', 'Приход'), ('expense', 'Расход')], default='expense', verbose_name="Тип")
    amount_fact = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Фактическая сумма")
    date_fact = models.DateField(null=True, blank=True, verbose_name="Фактическая дата")
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='cashless', verbose_name="Способ оплаты")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    
    def save(self, *args, **kwargs):
        # Авто-дата при оплате
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


class Document(TimeStampedModel): # <-- НАСЛЕДУЕМСЯ ОТ TimeStampedModel
    """Документы"""
    DOC_TYPE_CHOICES = [('invoice', 'Счет'), ('act', 'Акт'), ('payment_order', 'Платежка'), ('contract', 'Договор'), ('waybill', 'Накладная')]
    
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents', verbose_name="Платеж")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents', verbose_name="Заказ")
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, verbose_name="Тип документа")
    number = models.CharField(max_length=100, verbose_name="Номер документа")
    date = models.DateField(verbose_name="Дата документа")
    file = models.FileField(upload_to='documents/%Y/%m/', blank=True, verbose_name="Файл")
    
    def __str__(self):
        return f"{self.get_doc_type_display()} №{self.number}"
    
    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ['-date']