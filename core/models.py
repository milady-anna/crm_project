# core/models.py
from django.db import models

class TimeStampedModel(models.Model):
    """Абстрактная модель: добавляет даты создания и обновления"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        abstract = True  # Это важно: Django не создаст для этого таблицу в БД