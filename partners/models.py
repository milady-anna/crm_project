from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Client(models.Model):
    """Заказчики (те, кто покупает у нас мерч)"""
    name = models.CharField(max_length=200, verbose_name="Название компании")
    contact_person = models.CharField(max_length=200, blank=True, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    requisites = models.TextField(blank=True, verbose_name="Реквизиты")
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.20"),
        verbose_name="Наценка по умолчанию",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Заказчик"
        verbose_name_plural = "Заказчики"
        ordering = ["name"]


class Contractor(models.Model):
    """Подрядчики (те, кто поставляет нам товары/услуги)"""
    name = models.CharField(max_length=200, verbose_name="Название компании / ИП")
    contact_person = models.CharField(max_length=200, blank=True, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    payment_details = models.TextField(blank=True, verbose_name="Реквизиты оплаты")
    rating = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Рейтинг надёжности (1-5)",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Подрядчик"
        verbose_name_plural = "Подрядчики"
        ordering = ["name"]
