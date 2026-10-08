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
    
    def __str__(self):
        return self.name
    
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
    
    def __str__(self):
        return f"Заказ {self.number} ({self.client})"
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # При создании заказа автоматически устанавливаем первый этап
        if not self.pk and not self.current_stage:
            # Берем первый этап из шаблонов типа заказа
            first_template = self.order_type.ordertypetemplate_set.select_related('template__default_stage').order_by('order_index').first()
            if first_template and first_template.template.default_stage:
                self.current_stage = first_template.template.default_stage
        
        super().save(*args, **kwargs)

    @property
    def contract_amount_calculated(self):
        """Сумма по договору = сумма всех позиций заказа"""
        total = 0
        for item in self.items.all():
            total += item.quantity * item.price
        return round(total, 2)

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
            
            if not pending and not self.deadline_fact:
                Order.objects.filter(pk=self.pk).update(deadline_fact=timezone.now().date())

    @property
    def contract_amount_calculated(self):
        """Сумма по договору = сумма всех позиций заказа"""
        total = 0
        for item in self.items.all():
            total += item.quantity * item.price
        return round(total, 2)

 

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
    
    # НОВОЕ: Номер внутри этапа (1, 2, 3...)
    index_in_stage = models.IntegerField(default=0, verbose_name="Номер внутри этапа")
    
    def __str__(self):
        return f"{self.stage.name} #{self.index_in_stage}: {self.name}"
    
    class Meta:
        ordering = ['stage__order_index', 'index_in_stage']
        verbose_name = "Подэтап"
        verbose_name_plural = "Подэтапы"

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
    product = models.ForeignKey('products.OurProduct', on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.IntegerField(default=1, verbose_name="Количество")
    markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30.00, verbose_name="Наценка (%)")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена за единицу (итог)")
    cost_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Себестоимость (рассчитана)")
    variant = models.CharField(max_length=100, blank=True, verbose_name="Вариант (цвет/размер)")
    
    def __str__(self):
        return f"{self.product.name} × {self.quantity}"
    
    @property
    def total(self):
        return self.quantity * self.price

    def recalculate(self):
        """Пересчитывает себестоимость и цену на основе СОБСТВЕННЫХ компонентов позиции"""
        new_cost = sum(c.quantity * c.unit_price for c in self.components.all())
        self.cost_value = round(new_cost, 2)
        self.price = round(self.cost_value * (1 + self.markup_percent / 100), 2)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs) # Сначала сохраняем, чтобы получить ID
        
        if is_new:
            # КОПИРУЕМ глобальную спецификацию в этот конкретный заказ
            from products.models import ProductComponent
            for comp in ProductComponent.objects.filter(our_product=self.product):
                OrderItemComponent.objects.create(
                    order_item=self,
                    supplier_product=comp.supplier_product,
                    quantity=comp.quantity,
                    unit_price=comp.supplier_product.unit_price, # snapshot цены
                    substage_template=comp.substage_template
                )
        
        self.recalculate()
        # Обновляем только цены, чтобы не вызвать бесконечный цикл save()
        OrderItem.objects.filter(pk=self.pk).update(cost_value=self.cost_value, price=self.price)
        
        # Пересчитываем бюджет (если сервис готов)
        try:
            from finance.services import build_budget_for_order_item
            build_budget_for_order_item(self)
        except ImportError:
            pass

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"


class OrderItemComponent(models.Model):
    """Состав конкретной позиции заказа (Снимок спецификации)"""
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='components', verbose_name="Позиция заказа")
    supplier_product = models.ForeignKey('products.SupplierProduct', on_delete=models.PROTECT, verbose_name="Товар/услуга поставщика")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name="Количество")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена за единицу (на момент заказа)")
    substage_template = models.ForeignKey('SubstageTemplate', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Шаблон подэтапа")

    def __str__(self):
        return f"{self.supplier_product.name} ({self.quantity} шт.)"

    class Meta:
        verbose_name = "Компонент позиции"
        verbose_name_plural = "Компоненты позиций"


    class Meta:
        verbose_name = "Подэтап"
        verbose_name_plural = "Подэтапы"


class SubstageTemplateDocument(models.Model):  # <-- Без отступа! С самого начала строки
    substage_template = models.ForeignKey(
        SubstageTemplate,
        on_delete=models.CASCADE,
        related_name='template_documents',
        verbose_name="Шаблон подэтапа"
    )
    document_template = models.ForeignKey(
        'documents.DocumentTemplate',
        on_delete=models.CASCADE,
        verbose_name="Шаблон документа"
    )
    
    def __str__(self):
        return f"{self.substage_template.name} → {self.document_template.name}"
    
    class Meta:
        verbose_name = "Документ шаблона подэтапа"
        verbose_name_plural = "Документы шаблона подэтапа"
        unique_together = ('substage_template', 'document_template')