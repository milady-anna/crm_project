from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from partners.models import Client
from products.models import OurProduct, ProductComponent


# ============================================
# СПРАВОЧНИКИ (их заполняет руководитель в админке)
# ============================================

class Stage(models.Model):
    """Этап заказа. Один этап = одна колонка канбан-доски."""
    name = models.CharField(max_length=100, verbose_name="Название этапа")
    order_index = models.IntegerField(default=0, verbose_name="Порядок отображения")
    is_final = models.BooleanField(default=False, verbose_name="Финальный этап")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Этап"
        verbose_name_plural = "Этапы"
        ordering = ["order_index"]


class SubstageTemplate(models.Model):
    """Шаблон подэтапа: название, подсказка и этап, к которому он относится."""
    name = models.CharField(max_length=200, verbose_name="Название задачи")
    hint = models.TextField(blank=True, verbose_name="Подсказка менеджеру")
    default_stage = models.ForeignKey(Stage, on_delete=models.PROTECT, verbose_name="Этап")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Шаблон подэтапа"
        verbose_name_plural = "Шаблоны подэтапов"
        ordering = ["default_stage__order_index", "name"]


class OrderType(models.Model):
    """Тип заказа (Болванка, Россия, Китай...). Определяет набор подэтапов."""
    name = models.CharField(max_length=100, verbose_name="Название типа")
    description = models.TextField(blank=True, verbose_name="Описание")
    templates = models.ManyToManyField(
        SubstageTemplate, through="OrderTypeTemplate", blank=True, verbose_name="Базовые задачи"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тип заказа"
        verbose_name_plural = "Типы заказов"


class OrderTypeTemplate(models.Model):
    """Какие подэтапы входят в тип заказа, в каком порядке и на сколько дней."""
    order_type = models.ForeignKey(OrderType, on_delete=models.CASCADE, verbose_name="Тип заказа")
    template = models.ForeignKey(SubstageTemplate, on_delete=models.CASCADE, verbose_name="Шаблон задачи")
    duration_days = models.PositiveIntegerField(default=1, verbose_name="Длительность (дней)")
    order_index = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    def __str__(self):
        return f"{self.template.name} для {self.order_type.name}"

    class Meta:
        verbose_name = "Задача типа заказа"
        verbose_name_plural = "Задачи типа заказа"
        ordering = ["order_index", "id"]
        constraints = [
            models.UniqueConstraint(fields=["order_type", "template"], name="unique_template_per_order_type")
        ]


# ============================================
# РАБОЧИЕ ТАБЛИЦЫ
# ============================================

class Order(models.Model):
    number = models.CharField(max_length=50, unique=True, verbose_name="Номер заказа")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, verbose_name="Заказчик")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Менеджер")
    order_type = models.ForeignKey(OrderType, on_delete=models.PROTECT, verbose_name="Тип заказа")
    current_stage = models.ForeignKey(
        Stage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Текущий этап (авто)"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    deadline_plan = models.DateField(verbose_name="Плановый дедлайн")
    deadline_fact = models.DateField(null=True, blank=True, verbose_name="Фактическая дата завершения")

    contract_number = models.CharField(max_length=100, blank=True, verbose_name="Номер договора")

    def __str__(self):
        return f"Заказ {self.number} ({self.client})"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    @property
    def contract_amount_calculated(self):
        """Сумма по договору = сумма всех позиций заказа."""
        return sum((item.total for item in self.items.all()), Decimal("0"))

    def update_current_stage(self):
        """Пересчёт текущего этапа по незавершённым подэтапам."""
        if not self.substages.exists():
            return  # подэтапов нет - заказ не трогаем (иначе он «завершится» сам)

        pending = (
            self.substages.exclude(status="completed")
            .select_related("stage")
            .order_by("stage__order_index", "index_in_stage", "id")
            .first()
        )
        if pending:
            new_stage_id = pending.stage_id
            new_fact = None  # заказ снова в работе
        else:
            final = Stage.objects.filter(is_final=True).first()
            new_stage_id = final.pk if final else self.current_stage_id
            new_fact = self.deadline_fact or timezone.localdate()

        Order.objects.filter(pk=self.pk).update(current_stage_id=new_stage_id, deadline_fact=new_fact)
        self.current_stage_id = new_stage_id
        self.deadline_fact = new_fact


class Substage(models.Model):
    """Подэтап конкретного заказа. Это КОПИЯ шаблона: её можно менять, удалять
    и добавлять свои - шаблон и другие заказы не затрагиваются."""
    STATUS_CHOICES = [("not_started", "Не начата"), ("in_progress", "В работе"), ("completed", "Выполнена")]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="substages", verbose_name="Заказ")
    template = models.ForeignKey(
        SubstageTemplate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Шаблон"
    )
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, verbose_name="Этап")

    name = models.CharField(max_length=200, verbose_name="Название задачи")
    hint = models.TextField(blank=True, verbose_name="Подсказка")
    duration_days = models.PositiveIntegerField(default=1, verbose_name="Длительность (дней)")
    deadline = models.DateField(null=True, blank=True, verbose_name="Дедлайн")
    completed_date = models.DateField(null=True, blank=True, verbose_name="Дата выполнения")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_started", verbose_name="Статус")
    index_in_stage = models.PositiveIntegerField(default=0, verbose_name="Номер внутри этапа")

    def __str__(self):
        return f"{self.stage.name} #{self.index_in_stage}: {self.name}"

    class Meta:
        ordering = ["stage__order_index", "index_in_stage", "id"]
        verbose_name = "Подэтап в заказе"
        verbose_name_plural = "Подэтапы в заказе"

    def save(self, *args, **kwargs):
        if self.status == "completed":
            if not self.completed_date:
                self.completed_date = timezone.localdate()
        else:
            self.completed_date = None
        super().save(*args, **kwargs)
        self.order.update_current_stage()

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        order.update_current_stage()


class OrderItem(models.Model):
    """Товар в заказе. Цена = себестоимость по спецификации заказа + наценка."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ")
    product = models.ForeignKey(OurProduct, on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    markup_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("30.00"), verbose_name="Наценка (%)"
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Цена за единицу (итог)",
        help_text="Если у товара есть спецификация - считается сама (себестоимость + наценка). "
                  "Если спецификации нет - вводится вручную.",
    )
    cost_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Себестоимость (рассчитана)"
    )
    variant = models.CharField(max_length=100, blank=True, verbose_name="Вариант (цвет/размер)")

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"

    @property
    def total(self):
        return self.quantity * self.price

    def recalculate(self):
        """Считает себестоимость и цену по СОБСТВЕННЫМ компонентам позиции."""
        components = list(self.components.all())
        if not components:
            return  # спецификации нет - цена остаётся такой, как ввёл менеджер
        cost = sum((c.quantity * c.unit_price for c in components), Decimal("0"))
        markup = Decimal(str(self.markup_percent))
        self.cost_value = round(cost, 2)
        self.price = round(self.cost_value * (1 + markup / 100), 2)

    def refresh_prices(self):
        """Пересчитать и записать цены (без повторного вызова save())."""
        self.recalculate()
        OrderItem.objects.filter(pk=self.pk).update(cost_value=self.cost_value, price=self.price)

    def copy_components_from_product(self):
        """Копирует спецификацию товара в позицию (снимок цен на момент заказа)."""
        OrderItemComponent.objects.bulk_create([
            OrderItemComponent(
                order_item=self,
                supplier_product=comp.supplier_product,
                quantity=comp.quantity,
                unit_price=comp.supplier_product.unit_price,
                substage_template=comp.substage_template,
            )
            for comp in ProductComponent.objects.filter(our_product=self.product)
            .select_related("supplier_product")
        ])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.copy_components_from_product()
        self.refresh_prices()
        # Бюджет здесь НЕ строим: это делает orders.services.sync_order
        # после того, как в заказе есть и товары, и подэтапы.


class OrderItemComponent(models.Model):
    """Состав конкретной позиции заказа (снимок спецификации)"""
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="components", verbose_name="Позиция заказа"
    )
    supplier_product = models.ForeignKey(
        "products.SupplierProduct", on_delete=models.PROTECT, verbose_name="Товар/услуга поставщика"
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1, verbose_name="Количество на 1 шт."
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Цена за единицу (на момент заказа)"
    )
    substage_template = models.ForeignKey(
        SubstageTemplate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Шаблон подэтапа"
    )

    def __str__(self):
        return f"{self.supplier_product.name} ({self.quantity})"

    class Meta:
        verbose_name = "Компонент позиции"
        verbose_name_plural = "Компоненты позиций"


class SubstageTemplateDocument(models.Model):
    """Какие шаблоны документов предлагать на каком подэтапе."""
    substage_template = models.ForeignKey(
        SubstageTemplate, on_delete=models.CASCADE, related_name="template_documents",
        verbose_name="Шаблон подэтапа",
    )
    document_template = models.ForeignKey(
        "documents.DocumentTemplate", on_delete=models.CASCADE, verbose_name="Шаблон документа"
    )

    def __str__(self):
        return f"{self.substage_template.name} → {self.document_template.name}"

    class Meta:
        verbose_name = "Документ шаблона подэтапа"
        verbose_name_plural = "Документы шаблона подэтапа"
        unique_together = ("substage_template", "document_template")
