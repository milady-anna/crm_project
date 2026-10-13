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
    default_duration_days = models.PositiveIntegerField(
        default=1, verbose_name="Длительность по умолчанию (дней)"
    )
    hint = models.TextField(blank=True, verbose_name="Подсказка менеджеру")
    default_stage = models.ForeignKey(
        Stage, on_delete=models.PROTECT, verbose_name="Этап"
    )

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
        SubstageTemplate,
        through="OrderTypeTemplate",
        blank=True,
        verbose_name="Базовые задачи",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тип заказа"
        verbose_name_plural = "Типы заказов"


class OrderTypeTemplate(models.Model):
    """Какие подэтапы входят в тип заказа, в каком порядке и на сколько дней."""

    order_type = models.ForeignKey(
        OrderType, on_delete=models.CASCADE, verbose_name="Тип заказа"
    )
    template = models.ForeignKey(
        SubstageTemplate, on_delete=models.CASCADE, verbose_name="Шаблон задачи"
    )
    duration_days = models.PositiveIntegerField(
        default=1, verbose_name="Длительность (дней)"
    )
    order_index = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    def __str__(self):
        return f"{self.template.name} для {self.order_type.name}"

    class Meta:
        verbose_name = "Задача типа заказа"
        verbose_name_plural = "Задачи типа заказа"
        ordering = ["order_index", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order_type", "template"], name="unique_template_per_order_type"
            )
        ]


# ============================================
# РАБОЧИЕ ТАБЛИЦЫ
# ============================================


class Order(models.Model):
    number = models.CharField(max_length=50, unique=True, verbose_name="Номер заказа")
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, verbose_name="Заказчик"
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Менеджер"
    )
    order_type = models.ForeignKey(
        OrderType, on_delete=models.PROTECT, verbose_name="Тип заказа"
    )
    current_stage = models.ForeignKey(
        Stage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Текущий этап (авто)",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    deadline_plan = models.DateField(verbose_name="Плановый дедлайн")
    deadline_fact = models.DateField(
        null=True, blank=True, verbose_name="Фактическая дата завершения"
    )

    contract_number = models.CharField(
        max_length=100, blank=True, verbose_name="Номер договора"
    )
    brandbook_url = models.URLField(
        max_length=500, blank=True, verbose_name="Ссылка на брендбук для этого заказа"
    )
    contract_url = models.URLField(
        max_length=500, blank=True, verbose_name="Ссылка на договор (облако)"
    )
    kp_url = models.URLField(
        max_length=500, blank=True, verbose_name="Ссылка на КП (облако)"
    )
    contract_file = models.FileField(
        upload_to="orders/contracts/", null=True, blank=True, verbose_name="Файл договора"
    )
    kp_file = models.FileField(
        upload_to="orders/kp/", null=True, blank=True, verbose_name="Файл КП"
    )
    prepayment_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        verbose_name="Процент предоплаты (%)",
    )

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Автозаполнение брендбука из клиента
        if is_new and not self.brandbook_url:
            self.brandbook_url = self.client.brandbook_url

        super().save(*args, **kwargs)

        # Создание подэтапов только при первом сохранении
        if is_new:
            from .services import create_substages_for_order

            create_substages_for_order(self)

    def __str__(self):
        return f"Заказ {self.number} ({self.client})"

    @property
    def progress_percent(self):
        """Прогресс заказа в % на основе веса (длительности) выполненных подэтапов"""
        substages = self.substages.all()
        if not substages.exists():
            return 0

        total_weight = sum(s.duration_days for s in substages)
        if total_weight == 0:
            return 0

        completed_weight = sum(
            s.duration_days for s in substages if s.status == "completed"
        )
        return round((completed_weight / total_weight) * 100)

    @property
    def is_completed(self):
        """Заказ завершён, если все подэтапы выполнены"""
        if not self.substages.exists():
            return False
        return all(s.status == "completed" for s in self.substages.all())

    @property
    def has_overdue_substages(self):
        """Есть ли просроченные подэтапы"""
        from django.utils import timezone

        today = timezone.localdate()
        return self.substages.filter(
            status__in=["not_started", "in_progress"], deadline__lt=today
        ).exists()

    @property
    def nearest_deadline(self):
        """Ближайший дедлайн среди незавершённых подэтапов"""
        from django.utils import timezone

        today = timezone.localdate()
        nearest = (
            self.substages.filter(status__in=["not_started", "in_progress"])
            .order_by("deadline")
            .first()
        )
        return nearest.deadline if nearest else today

    @property
    def total_expenses(self):
        """Сумма расходов по заказу"""
        from finance.models import BudgetItem

        return (
            BudgetItem.objects.filter(order=self, flow_type="expense").aggregate(
                total=models.Sum("amount_plan")
            )["total"]
            or 0
        )

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

        Order.objects.filter(pk=self.pk).update(
            current_stage_id=new_stage_id, deadline_fact=new_fact
        )
        self.current_stage_id = new_stage_id
        self.deadline_fact = new_fact


class Substage(models.Model):
    """Подэтап конкретного заказа. Это КОПИЯ шаблона: её можно менять, удалять
    и добавлять свои - шаблон и другие заказы не затрагиваются."""

    STATUS_CHOICES = [
        ("not_started", "Не начата"),
        ("in_progress", "В работе"),
        ("completed", "Выполнена"),
    ]

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="substages", verbose_name="Заказ"
    )
    template = models.ForeignKey(
        SubstageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Шаблон",
    )
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, verbose_name="Этап")

    name = models.CharField(max_length=200, verbose_name="Название задачи")
    hint = models.TextField(blank=True, verbose_name="Подсказка")
    duration_days = models.PositiveIntegerField(
        default=1, verbose_name="Длительность (дней)"
    )
    deadline = models.DateField(null=True, blank=True, verbose_name="Дедлайн")
    completed_date = models.DateField(
        null=True, blank=True, verbose_name="Дата выполнения"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="not_started",
        verbose_name="Статус",
    )
    index_in_stage = models.PositiveIntegerField(
        default=0, verbose_name="Номер внутри этапа"
    )

    def __str__(self):
        return f"{self.stage.name} #{self.index_in_stage}: {self.name}"

    class Meta:
        ordering = ["stage__order_index", "index_in_stage", "id"]
        verbose_name = "Подэтап в заказе"
        verbose_name_plural = "Подэтапы в заказе"

    def save(self, *args, **kwargs):
        # Если подэтап создан из шаблона, копируем имя и подсказку, чтобы они были актуальны
        if self.template and not self.name:
            self.name = self.template.name
        if self.template and not self.hint:
            self.hint = self.template.hint

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

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ"
    )
    product = models.ForeignKey(
        OurProduct, on_delete=models.PROTECT, verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    markup_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("30.00"),
        verbose_name="Наценка (%)",
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.00,
        verbose_name="Налоговая ставка (%)",
        help_text="Например, 20 для НДС. Можно будет брать из товара в будущем.",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Цена за единицу (итог)",
        help_text="Если у товара есть спецификация - считается сама (себестоимость + наценка). "
        "Если спецификации нет - вводится вручную.",
    )
    cost_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Цена подрядчика за 1 шт. (расчётная)",
    )
    manual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Цена подрядчика вручную (за 1 шт.)",
        help_text="Если заполнено — используется вместо расчёта по компонентам "
        "(цены поставщиков в базе ориентировочные).",
    )

    @property
    def tax_amount(self):
        """Сумма налога в позиции (цена уже включает налог, выделяем «в том числе»)"""
        rate = Decimal(str(self.tax_rate))
        if rate <= 0:
            return Decimal("0.00")
        return round(self.total - self.total / (1 + rate / 100), 2)

    @property
    def net_markup_amount(self):
        """Валовая маржа: выручка минус себестоимость спецификации."""
        return round(self.total - (self.quantity * self.cost_value), 2)

    @property
    def margin_percent(self):
        """Маржинальность в % от выручки (безопасно при нулевой цене)."""
        if self.total == 0:
            return Decimal("0")
        return round(self.net_markup_amount / self.total * 100, 2)

    @property
    def markup_percent_effective(self):
        """Фактическая наценка к себестоимости в процентах."""
        base = self.quantity * self.cost_value
        if base == 0:
            return Decimal("0")
        return round(self.net_markup_amount / base * 100, 2)

    @property
    def net_total(self):
        """Цена подрядчика по всей позиции (без наценки и налога)."""
        return round(self.quantity * self.cost_value, 2)

    @property
    def markup_total_percent(self):
        """Наценка итого, % = (Итого - Налог - Цена подрядчика) / Цена подрядчика × 100.

        По сути это фактическая наценка к цене подрядчика с учётом всех
        ручных правок цены/количества (может отличаться от поля markup_percent,
        если менеджер правил итоговую цену вручную).
        """
        base = self.net_total
        if base == 0:
            return Decimal("0")
        return round((self.total - self.tax_amount - base) / base * 100, 2)

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"

    @property
    def total(self):
        return self.quantity * self.price

    def recalculate(self):
        """Считает себестоимость и цену по СОБСТВЕННЫМ компонентам позиции.

        Цена подрядчика (cost_value) — это сумма компонентов на 1 штуку.
        Менеджер может вручную задать цену подрядчика (manual_cost) — тогда
        она имеет приоритет над расчётом по компонентам (цены поставщиков
        в базе ориентировочные и часто меняются).

        Итоговая цена за единицу = цена подрядчика × (1 + наценка%).
        Налог выделяется «в том числе» из итоговой цены.
        """
        components = list(self.components.all())
        if self.manual_cost is not None:
            unit_cost = Decimal(str(self.manual_cost))
        elif components:
            unit_cost = sum(
                (c.quantity * c.unit_price for c in components), Decimal("0")
            )
        else:
            # спецификации нет и ручной цены нет - цена остаётся как есть
            return
        self.cost_value = round(unit_cost, 2)
        markup = Decimal(str(self.markup_percent or 0))
        self.price = round(self.cost_value * (1 + markup / 100), 2)

    def refresh_prices(self):
        """Пересчитать и записать цены (без повторного вызова save())."""
        self.recalculate()
        OrderItem.objects.filter(pk=self.pk).update(
            cost_value=self.cost_value, price=self.price
        )

    def copy_components_from_product(self):
        """Копирует спецификацию товара в позицию (снимок цен на момент заказа)."""
        OrderItemComponent.objects.bulk_create(
            [
                OrderItemComponent(
                    order_item=self,
                    supplier_product=comp.supplier_product,
                    quantity=comp.quantity,
                    unit_price=comp.supplier_product.unit_price,
                    substage_template=comp.substage_template,
                )
                for comp in ProductComponent.objects.filter(
                    our_product=self.product
                ).select_related("supplier_product")
            ]
        )

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
        OrderItem,
        on_delete=models.CASCADE,
        related_name="components",
        verbose_name="Позиция заказа",
    )
    supplier_product = models.ForeignKey(
        "products.SupplierProduct",
        on_delete=models.PROTECT,
        verbose_name="Товар/услуга поставщика",
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1, verbose_name="Количество на 1 шт."
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Цена за единицу (на момент заказа)",
    )
    substage_template = models.ForeignKey(
        SubstageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Шаблон подэтапа",
    )

    def __str__(self):
        return f"{self.supplier_product.name} ({self.quantity})"

    class Meta:
        verbose_name = "Компонент позиции"
        verbose_name_plural = "Компоненты позиций"


class SubstageTemplateDocument(models.Model):
    """Какие шаблоны документов предлагать на каком подэтапе."""

    substage_template = models.ForeignKey(
        SubstageTemplate,
        on_delete=models.CASCADE,
        related_name="template_documents",
        verbose_name="Шаблон подэтапа",
    )
    document_template = models.ForeignKey(
        "documents.DocumentTemplate",
        on_delete=models.CASCADE,
        verbose_name="Шаблон документа",
    )

    def __str__(self):
        return f"{self.substage_template.name} → {self.document_template.name}"

    class Meta:
        verbose_name = "Документ шаблона подэтапа"
        verbose_name_plural = "Документы шаблона подэтапа"
        unique_together = ("substage_template", "document_template")


class OrderComment(models.Model):
    """Внутренние комментарии к заказу"""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="comments", verbose_name="Заказ"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Автор"
    )
    text = models.TextField(verbose_name="Текст комментария")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Комментарий к заказу"
        verbose_name_plural = "Комментарии к заказу"

    def __str__(self):
        return f"Комментарий к {self.order.number} от {self.author}"
