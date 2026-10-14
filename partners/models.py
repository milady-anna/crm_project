from decimal import Decimal
from phonenumber_field.modelfields import PhoneNumberField

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Client(models.Model):
    """Заказчики (те, кто покупает у нас мерч)"""

    name = models.CharField(max_length=200, verbose_name="Название компании")
    contact_person = models.CharField(
        max_length=200, blank=True, verbose_name="Контактное лицо"
    )
    phone = PhoneNumberField(verbose_name="Номер телефона", blank=True)
    email = models.EmailField(blank=True, verbose_name="Email")
    requisites = models.TextField(blank=True, verbose_name="Реквизиты")
    STATUS_CHOICES = [
        ("potential", "Потенциальный (нет договора)"),
        ("current", "Текущий (договор заключен)"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="potential",
        verbose_name="Статус клиента",
    )
    brandbook_url = models.URLField(
        max_length=500, blank=True, verbose_name="Ссылка на брендбук заказчика (облако)"
    )
    default_markup_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30.00,
        verbose_name="Наценка по умолчанию (%)",
    )

    def phone_display(self):
        """Возвращает номер в едином формате +7XXXXXXXXXX"""
        if self.phone:
            try:
                return self.phone.as_e164  # PhoneNumberField
            except AttributeError:
                return str(self.phone)
        return "—"

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Заказчик"
        verbose_name_plural = "Заказчики"
        ordering = ["name"]


class Contractor(models.Model):
    """Подрядчики (те, кто поставляет нам товары/услуги)"""

    name = models.CharField(max_length=200, verbose_name="Название компании / ИП")
    contact_person = models.CharField(
        max_length=200, blank=True, verbose_name="Контактное лицо"
    )
    phone = PhoneNumberField(verbose_name="Номер телефона", blank=True)
    payment_details = models.TextField(blank=True, verbose_name="Реквизиты оплаты")
    address = models.TextField(blank=True, verbose_name="Адрес")
    comment = models.TextField(blank=True, verbose_name="Примечание")
    rating = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name="Рейтинг надёжности (1-5)",
    )

    def update_rating(self):
        """Пересчитывает средний рейтинг на основе отзывов"""
        from partners.models import ContractorReview

        reviews = ContractorReview.objects.filter(contractor=self)
        if reviews.exists():
            avg = reviews.aggregate(models.Avg("rating"))["rating__avg"]
            self.rating = round(avg) if avg else 3
        else:
            self.rating = 0  # рейтинг по умолчанию

        Contractor.objects.filter(pk=self.pk).update(rating=self.rating)

    def phone_display(self):
        """Возвращает номер в едином формате +7XXXXXXXXXX"""
        if self.phone:
            try:
                return self.phone.as_e164  # PhoneNumberField
            except AttributeError:
                return str(self.phone)
        return "—"

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Подрядчик"
        verbose_name_plural = "Подрядчики"
        ordering = ["name"]


class ContractorReview(models.Model):
    """Оценка работы подрядчика менеджером после завершения этапа/заказа"""

    contractor = models.ForeignKey(
        "Contractor",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Подрядчик",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Заказ",
    )
    rating = models.IntegerField(
        choices=[(i, f"{i} звезда") for i in range(1, 6)], verbose_name="Оценка (1-5)"
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий менеджера")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата оценки")

    class Meta:
        verbose_name = "Оценка подрядчика"
        verbose_name_plural = "Оценки подрядчиков"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Оценка {self.contractor}: {self.rating}/5"
