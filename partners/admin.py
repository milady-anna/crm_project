from django.contrib import admin
from .models import Client, Contractor

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'status', 'default_markup_percent')
    list_filter = ('status',)
    search_fields = ('name', 'contact_person')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'contact_person', 'phone', 'email', 'status')
        }),
        ('Финансы', {
            'fields': ('default_markup_percent', 'brandbook_url')
        }),
        ('Реквизиты', {
            'fields': ('requisites',)
        }),
    )

@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'rating')
    search_fields = ('name', 'contact_person')