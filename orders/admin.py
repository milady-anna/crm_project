# orders/admin.py
from django.contrib import admin
from .models import Order, OrderItem, OrderItemComponent, OrderType, Stage, SubstageTemplate, SubstageTemplateDocument, OrderTypeTemplate, Substage


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ('product', 'quantity', 'markup_percent', 'price', 'variant')


class OrderItemComponentInline(admin.TabularInline):
    model = OrderItemComponent
    extra = 1
    fields = ('supplier_product', 'quantity', 'unit_price', 'substage_template')


class SubstageInline(admin.TabularInline):
    model = Substage
    extra = 0
    fields = ('name', 'stage', 'deadline', 'status', 'completed_date', 'index_in_stage')


class SubstageTemplateDocumentInline(admin.TabularInline):
    model = SubstageTemplateDocument
    extra = 1
    fields = ('document_template',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'client', 'manager', 'order_type', 'current_stage', 'deadline_plan', 'contract_amount_calculated')
    list_filter = ('order_type', 'current_stage', 'manager')
    search_fields = ('number', 'client__short_name', 'client__full_name')
    inlines = [OrderItemInline, SubstageInline]
    
    def contract_amount_calculated(self, obj):
        return f"{obj.contract_amount_calculated} ₽"
    contract_amount_calculated.short_description = "Сумма по договору"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'cost_value', 'markup_percent', 'price')
    inlines = [OrderItemComponentInline]


@admin.register(OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ('name', 'order_index', 'is_final')
    list_editable = ('order_index', 'is_final')
    ordering = ('order_index',)


# ВАЖНО: Только ОДИН такой класс!
@admin.register(SubstageTemplate)
class SubstageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_stage', 'hint')
    list_filter = ('default_stage',)
    inlines = [SubstageTemplateDocumentInline]


@admin.register(Substage)
class SubstageAdmin(admin.ModelAdmin):
    list_display = ('order', 'stage', 'index_in_stage', 'name', 'status', 'deadline')
    list_filter = ('stage', 'status')
    ordering = ('order', 'stage__order_index', 'index_in_stage')