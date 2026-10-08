from django.contrib import admin
from .models import OurProduct, SupplierProduct

@admin.register(OurProduct)
class OurProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sale_price', 'min_quantity', 'production_days')
    search_fields = ('name',)

@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    # Заменили contractor_name на contractor
    list_display = ('name', 'contractor', 'product_type', 'unit_price')
    list_filter = ('product_type', 'contractor')
    # Добавили поиск и по названию подрядчика через двойное подчеркивание
    search_fields = ('name', 'contractor__name') 