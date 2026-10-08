from django.db import models
from django.conf import settings
from partners.models import Client
from products.models import OurProduct


# ============================================
# СПРАВОЧНИКИ
# ============================================

class Stage(models.Model):
    """Этапы (колонки Канбан-доски)"""
    name = models.CharField(max_length=100, verbose_name="Название этапа")
    order_index = models.IntegerField(default=0, verbose_name="Порядок отображения")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Этап"
        verbose_name_plural = "Этапы"
        ordering = ['order_index']


class SubstageTemplate(models.Model):
    """Библиотека шаблонов задач (используется в разных типах заказов)"""
    name = models.CharField(max_length=200, verbose_name="Название задачи")
    default_stage = models.ForeignKey(
        Stage, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Этап по умолчанию"
    )
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Шаблон задачи"
        verbose_name_plural = "Шаблоны задач"


class OrderType(models.Model):
    """Типы заказов (Болванка, Россия, Китай)"""
    name = models.CharField(max_length=100, verbose_name="Название типа")
    description = models.TextField(blank=True, verbose_name="Описание")
    
    # Связь "Многие-ко-многим" с шаблонами через промежуточную таблицу
    templates = models.ManyToManyField(
        SubstageTemplate, 
        through='OrderTypeTemplate',
        related_name='order_types',
        blank=True,
        verbose_name="Базовые задачи для этого типа"
    )
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Тип заказа"
        verbose_name_plural = "Типы заказов"


class OrderTypeTemplate(models.Model):
    """Промежуточная таблица: какие шаблоны входят в тип заказа и с какими параметрами"""
    order_type = models.ForeignKey(OrderType, on_delete=models.CASCADE, verbose_name="Тип заказа")
    template = models.ForeignKey(SubstageTemplate, on_delete=models.CASCADE, verbose_name="Шаблон задачи")
    duration_days = models.IntegerField(default=1, verbose_name="Длительность задачи (дней)")
    order_index = models.IntegerField(default=0, verbose_name="Порядок выполнения")
    
    def __str__(self):
        return f"{self.template.name} для {self.order_type.name}"
    
    class Meta:
        verbose_name = "Настройка задачи для типа"
        verbose_name_plural = "Настройки задач для типов"
        ordering = ['order_index']


# ============================================
# РАБОЧИЕ ТАБЛИЦЫ
# ============================================

class Order(models.Model):
    """Заказ (шапка)"""
    number = models.CharField(max_length=50, verbose_name="Номер заказа")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, verbose_name="Заказчик")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Менеджер")
    order_type = models.ForeignKey(OrderType, on_delete=models.PROTECT, verbose_name="Тип заказа")
    
    # current_stage теперь будет обновляться автоматически!
    current_stage = models.ForeignKey(
        Stage, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Текущий этап (авто)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    deadline_plan = models.DateField(verbose_name="Плановый дедлайн")
    deadline_fact = models.DateField(null=True, blank=True, verbose_name="Фактическая дата завершения")
    
    contract_number = models.CharField(max_length=100, blank=True, verbose_name="Номер договора")
    contract_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма по договору")
    expenses_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма расходов")
    
    def __str__(self):
        return f"Заказ {self.number} ({self.client})"
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def update_current_stage(self):
        """Автоматически определяет текущий этап на основе подзадач"""
        # Ищем первую незавершенную подзадачу по порядку
        incomplete_substage = self.substages.exclude(status='completed').order_by('order_index').first()
        
        if incomplete_substage:
            # Если есть незавершенные задачи, этап = этап этой задачи
            self.current_stage = incomplete_substage.stage
        else:
            # Если все задачи выполнены, заказ на последнем этапе системы
            last_stage = Stage.objects.order_by('-order_index').first()
            self.current_stage = last_stage
            # И автоматически проставляем дату факта, если её нет
            if not self.deadline_fact:
                self.deadline_fact = date.today()
        
        # Сохраняем только измененные поля, чтобы не вызывать бесконечные циклы
        self.save(update_fields=['current_stage', 'deadline_fact'])


class Substage(models.Model):
    """Подэтапы (конкретные задачи в заказе)"""
    STATUS_CHOICES = [
        ('not_started', 'Не начата'),
        ('in_progress', 'В работе'),
        ('completed', 'Выполнена'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='substages', verbose_name="Заказ")
    template = models.ForeignKey(SubstageTemplate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Шаблон")
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, verbose_name="Этап")
    
    name = models.CharField(max_length=200, verbose_name="Название задачи")
    duration_days = models.IntegerField(default=1, verbose_name="Длительность (дней)")
    deadline = models.DateField(null=True, blank=True, verbose_name="Дедлайн")
    completed_date = models.DateField(null=True, blank=True, verbose_name="Дата выполнения")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started', verbose_name="Статус")
    order_index = models.IntegerField(default=0, verbose_name="Порядок в заказе")
    
    def __str__(self):
        return f"{self.name} ({self.order.number})"
    
    class Meta:
        verbose_name = "Подэтап"
        verbose_name_plural = "Подэтапы"
        ordering = ['order_index']

    # ПЕРЕОПРЕДЕЛЯЕМ СОХРАНЕНИЕ И УДАЛЕНИЕ
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # После сохранения подзадачи, пересчитываем этап заказа
        self.order.update_current_stage()

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        # После удаления подзадачи, тоже пересчитываем этап
        order.update_current_stage()
        

class OrderItem(models.Model):
    """Товары в заказе (состав)"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    product = models.ForeignKey(OurProduct, on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.IntegerField(default=1, verbose_name="Количество")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за единицу")
    
    def __str__(self):
        return f"{self.product.name} × {self.quantity}"
    
    @property
    def total(self):
        return self.quantity * self.price
    
    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"