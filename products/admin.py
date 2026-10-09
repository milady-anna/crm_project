# products/admin.py
from django.contrib import admin
from .models import OurProduct, ProductComponent, SupplierProduct


class ProductComponentInline(admin.TabularInline):
    """Спецификацию добавляем прямо на странице товара"""
    model = ProductComponent
    extra = 1
    fields = ("supplier_product", "quantity", "substage_template")


@admin.register(OurProduct)
class OurProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sale_price", "cost_display", "min_quantity", "production_days")
    search_fields = ("name",)
    inlines = [ProductComponentInline]

    @admin.display(description="Себестоимость")
    def cost_display(self, obj):
        return f"{obj.min_cost} ₽"


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ("name", "contractor", "product_type", "unit_price", "lead_time_days")
    list_filter = ("contractor", "product_type")
    search_fields = ("name", "contractor__name")
