from django import forms
from django.forms import inlineformset_factory
from orders.models import Order, OrderItem


class OrderCreateForm(forms.ModelForm):
    """Форма создания заказа"""

    class Meta:
        model = Order
        fields = [
            "number",
            "client",
            "manager",
            "order_type",
            "deadline_plan",
            "contract_number",
            "brandbook_url",
            "contract_url",
            "kp_url",
            "prepayment_percent",
        ]
        widgets = {
            "number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Например: 535636"}
            ),
            "client": forms.Select(attrs={"class": "form-select"}),
            "manager": forms.Select(attrs={"class": "form-select"}),
            "order_type": forms.Select(attrs={"class": "form-select"}),
            "deadline_plan": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "contract_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Номер договора (необязательно)",
                }
            ),
            "brandbook_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://..."}
            ),
            "contract_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://..."}
            ),
            "kp_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://..."}
            ),
            "prepayment_percent": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                }
            ),
        }


# Formset для позиций заказа
OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    fields=["product", "quantity", "markup_percent", "price"],
    extra=1,  # одна пустая строка по умолчанию
    can_delete=True,
    widgets={
        "product": forms.Select(attrs={"class": "form-select"}),
        "quantity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
        "markup_percent": forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01"}
        ),
        "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    },
)
