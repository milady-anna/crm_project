from django.contrib import admin
from .models import Client, Contractor

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'tax_rate')
    search_fields = ('name', 'contact_person')

@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'rating')
    search_fields = ('name', 'contact_person')