from django.contrib import admin
from .models import BudgetItem, Transaction, Document


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 1
    fields = ('amount_fact', 'date_fact', 'payment_method', 'status', 'comment')


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 1
    fields = ('doc_type', 'number', 'date', 'file')


@admin.register(BudgetItem)
class BudgetItemAdmin(admin.ModelAdmin):
    # Заменили 'status' на 'payment_state'
    list_display = ('order', 'component_name', 'contractor', 'amount_plan', 'date_plan', 'payment_state')
    list_filter = ('flow_type', 'order')
    search_fields = ('component_name', 'contractor__name')
    inlines = [TransactionInline]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('order', 'budget_item', 'amount_fact', 'date_fact', 'status', 'payment_method')
    list_filter = ('status', 'flow_type', 'payment_method')
    search_fields = ('order__number', 'comment')
    inlines = [DocumentInline]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('doc_type', 'number', 'date', 'transaction', 'order')
    list_filter = ('doc_type',)
    search_fields = ('number',)