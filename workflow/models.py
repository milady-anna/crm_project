from django.db import models

class Stage(models.Model):
    """Этапы (колонки Канбан-доски)"""
    name = models.CharField(max_length=100, verbose_name="Название этапа")
    order_index = models.IntegerField(default=0, verbose_name="Порядок отображения")
    is_final = models.BooleanField(default=False, verbose_name="Финальный этап") # Добавили по совету ревью
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Этап"
        verbose_name_plural = "Этапы"
        ordering = ['order_index']

class SubstageTemplate(models.Model):
    """Библиотека шаблонов задач"""
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