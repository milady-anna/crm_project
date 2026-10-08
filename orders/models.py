from django.db import models
from django.conf import settings
from django.utils import timezone
from partners.models import Client
from products.models import OurProduct

# ============================================
# СПРАВОЧНИКИ (Теперь только здесь, workflow удален)
# ============================================

class Stage(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название этапа")
    order_index = models.IntegerField(default=0, verbose_name="Порядок отображения")
    is_final = models.BooleanField(default=False, verbose_name="Финальный этап")
    
    def __str__(self): return self.name
    class Meta:
        verbose_name = "Этап"
        verbose_name_plural = "Этапы"
        ordering = ['order_index']

class SubstageTemplate(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название задачи")
    default_stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Этап по умолчанию")
    hint = models.CharField(max_length=200, blank=True, verbose_name="Подсказка")
    
    def __str__(self): return self.name
    class Meta:
        verbose_name = "Шаблон задачи"
        verbose_name_plural = "Шаблоны задач"

class OrderType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название типа")
    description = models.TextField(blank=True, verbose_name="Описание")
    templates = models.ManyToManyField(SubstageTemplate, through='OrderTypeTemplate', blank=True, verbose_name="Базовые задачи")
    
    def __str__(self): return self.name
    class Meta:
        verbose_name = "Тип заказа"
        verbose_name_plural = "Типы заказов"

class OrderTypeTemplate(models.Model):
    order_type = models.ForeignKey(OrderType, on_delete=models.CASCADE, verbose_name="Тип заказа")
    template = models.ForeignKey(SubstageTemplate, on_delete=models.CASCADE, verbose_name="Шаблон задачи")
    duration_days = models.IntegerField(default=1, verbose_name="Длительность (дней)")
    order_index = models.IntegerField(default=0, verbose_name="Порядок")
    
    def __str__(self): return f"{self.template.name} для {self.order_type.name}"
    class Meta:
        ordering = ['order_index']

# ============================================
# РАБОЧИЕ ТАБЛИЦЫ
# ============================================

class Order(models.Model):
    number = models.CharField(max_length=50, unique=True, verbose_name="Номер заказа")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, verbose_name="Заказчик")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Менеджер")
    order_type = models.ForeignKey(OrderType, on_delete=models.PROTECT, verbose_name="Тип заказа")
    current_stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Текущий этап")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    deadline_plan = models.DateField(verbose_name="Плановый дедлайн")
    deadline_fact = models.DateField(null=True, blank=True, verbose_name="Фактическая дата завершения")
    
    contract_number = models.CharField(max_length=100, blank=True, verbose_name="Номер договора")
    contract_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма по договору")
    # expenses_amount УДАЛЕН, так как считается динамически

    def __str__(self): return f"Заказ {self.number} ({self.client})"
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def update_current_stage(self):
        """Пересчет текущего этапа на основе незавершенных подэтапов"""
        pending = self.substages.exclude(status='completed').select_related('stage').order_by('stage__order_index', 'order_index').first()
        
        if pending:
            new_stage_id = pending.stage_id
        else:
            final = Stage.objects.filter(is_final=True).first()
            new_stage_id = final.pk if final else self.current_stage_id

        if new_stage_id != self.current_stage_id:
            Order.objects.filter(pk=self.pk).update(current_stage_id=new_stage_id)
            self.current_stage_id = new_stage_id
            
            # Если все завершено, ставим дату факта
            if not pending and not self.deadline_fact:
                Order.objects.filter(pk=self.pk).update(deadline_fact=timezone.now().date())

class Substage(models.Model):
    STATUS_CHOICES = [('not_started', 'Не начата'), ('in_progress', 'В работе'), ('completed', 'Выполнена')]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='substages', verbose_name="Заказ")
    template = models.ForeignKey(SubstageTemplate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Шаблон")
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, verbose_name="Этап")
    
    name = models.CharField(max_length=200, verbose_name="Название задачи")
    duration_days = models.IntegerField(default=1, verbose_name="Длительность (дней)")
    deadline = models.DateField(null=True, blank=True, verbose_name="Дедлайн")
    completed_date = models.DateField(null=True, blank=True, verbose_name="Дата выполнения")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started', verbose_name="Статус")
    order_index = models.IntegerField(default=0, verbose_name="Порядок в заказе")
    
    def __str__(self): return f"{self.name} ({self.order.number})"
    class Meta:
        ordering = ['order_index']

    def save(self, *args, **kwargs):
        if self.status == 'completed' and not self.completed_date:
            self.completed_date = timezone.now().date()
        elif self.status != 'completed':
            self.completed_date = None
        super().save(*args, **kwargs)
        self.order.update_current_stage()

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        order.update_current_stage()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    product = models.ForeignKey(OurProduct, on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.IntegerField(default=1, verbose_name="Количество")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за единицу")
    variant = models.CharField(max_length=100, blank=True, verbose_name="Вариант (цвет/размер)")
    
    def __str__(self): return f"{self.product.name} × {self.quantity}"
    
    @property
    def total(self): return self.quantity * self.price
    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"