# documents/models.py
from django.db import models


class DocumentTemplate(models.Model):
    """Шаблон документа (ссылка на файл в облаке)"""
    
    DOC_TYPE_CHOICES = [
        ('invoice', 'Счет'),
        ('act', 'Акт'),
        ('contract', 'Договор'),
        ('kp', 'КП (Коммерческое предложение)'),
        ('waybill', 'Накладная'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Название шаблона")
    
    doc_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        verbose_name="Тип документа"
    )
    
    order_type = models.ForeignKey(
        'orders.OrderType',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Тип заказа (пусто = универсальный)"
    )
    
    substage_template = models.ForeignKey(
        'workflow.SubstageTemplate',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Подэтап (пусто = в любой момент)"
    )
    
    url = models.URLField(verbose_name="Ссылка на файл в облаке")
    
    description = models.TextField(blank=True, verbose_name="Описание / Подсказка")
    
    def __str__(self):
        return f"{self.name} ({self.get_doc_type_display()})"
    
    class Meta:
        verbose_name = "Шаблон документа"
        verbose_name_plural = "Шаблоны документов"
        ordering = ['doc_type', 'name']