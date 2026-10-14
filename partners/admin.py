from django.contrib import admin
from .models import Client, Contractor


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "contact_person",
        "phone_display",  # ✅ Метод для отображения в списке
        "status",
        "default_markup_percent",
    )
    list_filter = ("status",)
    search_fields = ("name", "contact_person", "phone")

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": ("name", "contact_person", "phone", "email", "status")
            },  # ✅ phone, не phone_display
        ),
        ("Финансы", {"fields": ("default_markup_percent", "brandbook_url")}),
        ("Реквизиты", {"fields": ("requisites",)}),
    )


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "contact_person",
        "phone_display",  # ✅ Метод для отображения
        "rating",
        "address",
    )
    list_filter = ("rating",)  # ✅ Добавили фильтр по рейтингу
    search_fields = ("name", "contact_person", "phone", "address")

    fieldsets = (  # ✅ Добавили fieldsets для удобного редактирования
        (
            "Основная информация",
            {"fields": ("name", "contact_person", "phone", "address")},
        ),
        ("Финансы", {"fields": ("payment_details", "rating")}),
        (
            "Дополнительно",
            {"fields": ("comment",), "classes": ("collapse",)},  # Сворачиваемый блок
        ),
    )
