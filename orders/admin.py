# orders/admin.py
from django.contrib import admin

from finance.services import build_budget_for_order_item

from .models import (
    Order,
    OrderItem,
    OrderItemComponent,
    OrderType,
    Stage,
    SubstageTemplate,
    SubstageTemplateDocument,
    OrderTypeTemplate,
    Substage,
    OrderComment,
)
from .services import sync_order


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ("product", "quantity", "markup_percent", "tax_rate", "price")


class OrderItemComponentInline(admin.TabularInline):
    model = OrderItemComponent
    extra = 1
    fields = ("supplier_product", "quantity", "unit_price", "substage_template")


class SubstageInline(admin.TabularInline):
    model = Substage
    extra = 0
    fields = (
        "stage",
        "index_in_stage",
        "name",
        "hint",
        "duration_days",
        "deadline",
        "status",
        "completed_date",
    )
    readonly_fields = ("name", "hint", "deadline")  # Название и подсказка readonly
    ordering = ("stage__order_index", "index_in_stage")


class SubstageTemplateDocumentInline(admin.TabularInline):
    model = SubstageTemplateDocument
    extra = 1
    fields = ("document_template",)


class OrderTypeTemplateInline(admin.TabularInline):
    model = OrderTypeTemplate
    extra = 1
    fields = ("template", "duration_days", "order_index")


class OrderCommentInline(admin.TabularInline):
    """Комментарии к заказу прямо в карточке заказа"""

    model = OrderComment
    extra = 1
    fields = ("author", "text", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "client",
        "manager",
        "order_type",
        "current_stage",
        "deadline_plan",
        "contract_amount_calculated",
    )
    list_filter = ("order_type", "current_stage", "manager")
    search_fields = ("number", "client__name")
    inlines = [
        OrderItemInline,
        SubstageInline,
        OrderCommentInline,
    ]  # <-- ДОБАВИЛИ OrderCommentInline

    def contract_amount_calculated(self, obj):
        return f"{obj.contract_amount_calculated} ₽"

    contract_amount_calculated.short_description = "Сумма по договору"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "client", "manager", "order_type", "current_stage"
        ).prefetch_related("items")

    def get_changeform_initial_data(self, request):
        return {"manager": request.user.pk}

    def get_inline_instances(self, request, obj=None):
        # При создании заказа подэтапы не показываем: система создаст их сама по типу заказа
        instances = super().get_inline_instances(request, obj)
        if obj is None:
            instances = [i for i in instances if not isinstance(i, SubstageInline)]
        return instances

    def save_related(self, request, form, formsets, change):
        super().save_related(
            request, form, formsets, change
        )  # сохраняет товары и подэтапы из форм
        sync_order(form.instance, created=not change)

    def save_model(self, request, obj, form, change):
        """При смене клиента обновляем брендбук"""
        if not change:  # Только при создании
            if obj.client and obj.client.brandbook_url:
                obj.brandbook_url = obj.client.brandbook_url
        super().save_model(request, obj, form, change)

    @admin.display(description="Сумма по договору")
    def contract_amount_calculated(self, obj):
        return f"{obj.contract_amount_calculated} ₽"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "product",
        "quantity",
        "cost_value",
        "tax_rate",
        "tax_amount_display",
        "markup_percent",
        "net_markup_display",
        "price",
    )
    inlines = [OrderItemComponentInline]

    def tax_amount_display(self, obj):
        return f"{obj.tax_amount} ₽"

    tax_amount_display.short_description = "Сумма налога"

    def net_markup_display(self, obj):
        return f"{obj.net_markup_amount} ₽ ({obj.markup_percent_effective}%)"

    net_markup_display.short_description = "Наценка (чистая)"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)  # сохраняет компоненты
        item = form.instance
        item.refresh_prices()  # цена зависит от компонентов
        build_budget_for_order_item(item)  # и бюджет тоже


@admin.register(OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    inlines = [OrderTypeTemplateInline]


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("name", "order_index", "is_final")
    list_editable = ("order_index", "is_final")
    ordering = ("order_index",)


@admin.register(SubstageTemplate)
class SubstageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "default_stage")
    list_filter = ("default_stage",)
    search_fields = ("name",)
    inlines = [SubstageTemplateDocumentInline]


@admin.register(Substage)
class SubstageAdmin(admin.ModelAdmin):
    list_display = ("order", "stage", "index_in_stage", "name", "status", "deadline")
    list_filter = ("stage", "status")
    list_select_related = ("order", "stage")
    readonly_fields = ("completed_date",)
