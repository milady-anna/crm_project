from django.db import models

class Client(models.Model):
    """Заказчики (те, кто покупает у нас мерч)"""
    # id создается Django автоматически
    
    name = models.CharField(max_length=200, verbose_name="Название компании")
    contact_person = models.CharField(max_length=200, blank=True, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.20, 
        verbose_name="Ставка НДС (например, 0.20)"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Заказчик"
        verbose_name_plural = "Заказчики"


class Contractor(models.Model):
    """Подрядчики (те, кто поставляет нам товары/услуги)"""
    # id создается Django автоматически
    
    name = models.CharField(max_length=200, verbose_name="Название компании / ИП")
    contact_person = models.CharField(max_length=200, blank=True, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    rating = models.IntegerField(
        default=3, 
        verbose_name="Рейтинг надёжности (1-5)"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Подрядчик"
        verbose_name_plural = "Подрядчики"