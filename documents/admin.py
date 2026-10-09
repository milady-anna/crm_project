# documents/admin.py
from django.contrib import admin
from .models import DocumentTemplate


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'doc_type', 'order_type', 'url')
    list_filter = ('doc_type', 'order_type')
    search_fields = ('name', 'description')