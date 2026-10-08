from django.contrib import admin
from .models import (
    Stage, SubstageTemplate, OrderType, OrderTypeTemplate, 
    Order, Substage, OrderItem
)

# Inline для товаров
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ('product', 'quantity', 'price')

# Inline для задач в заказе
class SubstageInline(admin.TabularInline):
    model = Substage
    extra = 1
    fields = ('name', 'stage', 'duration_days', 'deadline', 'status', 'order_index')
    ordering = ('order_index',)

# Inline для настройки связи Типа заказа и Шаблонов
class OrderTypeTemplateInline(admin.TabularInline):
    model = OrderTypeTemplate
    extra = 1
    fields = ('template', 'duration_days', 'order_index')
    ordering = ('order_index',)


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ('name', 'order_index')
    ordering = ('order_index',)

@admin.register(SubstageTemplate)
class SubstageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_stage')
    list_filter = ('default_stage',)

@admin.register(OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    inlines = [OrderTypeTemplateInline] # Настраиваем задачи прямо внутри типа заказа

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'client', 'manager', 'order_type', 'current_stage', 'deadline_plan', 'contract_amount')
    list_filter = ('order_type', 'current_stage', 'manager')
    search_fields = ('number', 'client__name')
    inlines = [OrderItemInline, SubstageInline]