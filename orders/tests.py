from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from finance.models import BudgetItem
from orders.models import (
    Order, OrderItem, OrderType, OrderTypeTemplate, Stage, Substage, SubstageTemplate,
)
from orders.services import create_substages_for_order, sync_order
from partners.models import Client, Contractor
from products.models import OurProduct, ProductComponent, SupplierProduct


class OrdersBase(TestCase):
    """Общие данные: 2 этапа, 2 шаблона подэтапов, тип заказа, подрядчик и товар со спецификацией."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("manager", password="pw")
        cls.client_obj = Client.objects.create(name="ООО Ромашка")
        cls.stage1 = Stage.objects.create(name="Разработка КП", order_index=1)
        cls.stage2 = Stage.objects.create(name="Склад", order_index=2, is_final=True)
        cls.tpl1 = SubstageTemplate.objects.create(name="Согласовать макет", hint="Отправьте макет", default_stage=cls.stage1)
        cls.tpl2 = SubstageTemplate.objects.create(name="Приёмка на склад", default_stage=cls.stage2)
        cls.order_type = OrderType.objects.create(name="Россия")
        OrderTypeTemplate.objects.create(order_type=cls.order_type, template=cls.tpl2, order_index=2, duration_days=3)
        OrderTypeTemplate.objects.create(order_type=cls.order_type, template=cls.tpl1, order_index=1, duration_days=2)

        cls.contractor = Contractor.objects.create(name="Типография")
        cls.supplier_product = SupplierProduct.objects.create(
            contractor=cls.contractor, name="Печать", unit_price=Decimal("100.00")
        )
        cls.product = OurProduct.objects.create(name="Футболка")
        ProductComponent.objects.create(
            our_product=cls.product, supplier_product=cls.supplier_product,
            quantity=Decimal("1"), substage_template=cls.tpl1,
        )

    def make_order(self, number="1"):
        return Order.objects.create(
            number=number, client=self.client_obj, manager=self.user,
            order_type=self.order_type, deadline_plan=timezone.localdate() + timedelta(days=30),
        )


class SubstageCreationTests(OrdersBase):
    def test_substages_copied_from_order_type_in_order(self):
        order = self.make_order()
        create_substages_for_order(order)
        names = list(order.substages.values_list("name", flat=True))
        self.assertEqual(names, ["Согласовать макет", "Приёмка на склад"])

    def test_hint_is_copied_and_deadlines_are_chained(self):
        order = self.make_order()
        create_substages_for_order(order)
        first, second = order.substages.all()
        self.assertEqual(first.hint, "Отправьте макет")
        today = timezone.localdate()
        self.assertEqual(first.deadline, today + timedelta(days=2))
        self.assertEqual(second.deadline, today + timedelta(days=5))

    def test_second_call_does_not_duplicate(self):
        order = self.make_order()
        create_substages_for_order(order)
        create_substages_for_order(order)
        self.assertEqual(order.substages.count(), 2)

    def test_current_stage_is_first_stage_after_creation(self):
        order = self.make_order()
        create_substages_for_order(order)
        order.refresh_from_db()
        self.assertEqual(order.current_stage, self.stage1)


class StageProgressTests(OrdersBase):
    def setUp(self):
        self.order = self.make_order()
        create_substages_for_order(self.order)
        self.first, self.second = self.order.substages.all()

    def test_completing_first_stage_moves_order_forward(self):
        self.first.status = "completed"
        self.first.save()
        self.order.refresh_from_db()
        self.assertEqual(self.order.current_stage, self.stage2)
        self.assertIsNone(self.order.deadline_fact)

    def test_completing_everything_finishes_order(self):
        for s in (self.first, self.second):
            s.status = "completed"
            s.save()
        self.order.refresh_from_db()
        self.assertEqual(self.order.current_stage, self.stage2)
        self.assertEqual(self.order.deadline_fact, timezone.localdate())

    def test_reopening_clears_fact_date(self):
        for s in (self.first, self.second):
            s.status = "completed"
            s.save()
        self.second.status = "in_progress"
        self.second.save()
        self.order.refresh_from_db()
        self.assertIsNone(self.order.deadline_fact)

    def test_deleting_last_substage_does_not_finish_order(self):
        self.first.delete()
        self.second.delete()
        self.order.refresh_from_db()
        self.assertIsNone(self.order.deadline_fact)

    def test_completed_date_is_set_and_cleared(self):
        self.first.status = "completed"
        self.first.save()
        self.assertEqual(self.first.completed_date, timezone.localdate())
        self.first.status = "not_started"
        self.first.save()
        self.assertIsNone(self.first.completed_date)


class PricingTests(OrdersBase):
    def test_price_is_cost_plus_markup(self):
        order = self.make_order()
        item = OrderItem.objects.create(order=order, product=self.product, quantity=10)  # наценка по умолчанию 30%
        item.refresh_from_db()
        self.assertEqual(item.cost_value, Decimal("100.00"))
        self.assertEqual(item.price, Decimal("130.00"))
        self.assertEqual(order.contract_amount_calculated, Decimal("1300.00"))

    def test_components_are_a_snapshot(self):
        order = self.make_order()
        item = OrderItem.objects.create(order=order, product=self.product, quantity=1)
        self.supplier_product.unit_price = Decimal("500.00")
        self.supplier_product.save()
        item.refresh_prices()
        self.assertEqual(item.cost_value, Decimal("100.00"))  # цена в заказе не поменялась

    def test_manual_price_kept_when_product_has_no_spec(self):
        order = self.make_order()
        pen = OurProduct.objects.create(name="Ручка")
        item = OrderItem.objects.create(order=order, product=pen, quantity=5, price=Decimal("250.00"))
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal("250.00"))

    def test_new_product_can_be_created(self):
        product = OurProduct.objects.create(name="Кружка")
        self.assertEqual(product.min_cost, Decimal("0"))
        self.assertEqual(self.product.min_cost, Decimal("100.00"))


class BudgetTests(OrdersBase):
    def build_order(self):
        order = self.make_order()
        OrderItem.objects.create(order=order, product=self.product, quantity=10)
        sync_order(order, created=True)
        return order

    def test_budget_created_with_substage_and_date(self):
        order = self.build_order()
        budget = BudgetItem.objects.get(order=order)
        self.assertEqual(budget.amount_plan, Decimal("1000.00"))   # 10 шт * 1 * 100
        self.assertEqual(budget.contractor, self.contractor)
        self.assertEqual(budget.substage.name, "Согласовать макет")
        self.assertEqual(budget.date_plan, budget.substage.deadline)

    def test_resync_updates_amount_without_duplicates(self):
        order = self.build_order()
        item = order.items.get()
        item.quantity = 20
        item.save()
        sync_order(order)
        self.assertEqual(BudgetItem.objects.filter(order=order).count(), 1)
        self.assertEqual(BudgetItem.objects.get(order=order).amount_plan, Decimal("2000.00"))

    def test_payment_state_text(self):
        budget = BudgetItem.objects.get(order=self.build_order())
        self.assertEqual(budget.payment_state, "Не оплачено")

    def test_item_can_be_deleted(self):
        order = self.build_order()
        order.items.get().delete()
        self.assertEqual(BudgetItem.objects.filter(order=order).count(), 0)


class AdminSmokeTests(OrdersBase):
    """Открываем страницы админки так, как это делает человек: ловит падения, которые не видно в моделях."""

    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser("boss", "b@x.ru", "pw")
        self.client.force_login(self.admin_user)

    def test_all_changelists_and_add_pages_open(self):
        from django.contrib import admin
        from django.urls import reverse
        for model in admin.site._registry:
            opts = model._meta
            if opts.app_label in ("auth", "contenttypes", "sessions", "admin"):
                continue
            for name in ("changelist", "add"):
                url = reverse(f"admin:{opts.app_label}_{opts.model_name}_{name}")
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    def test_search_in_order_admin(self):
        self.make_order("Z-7")
        response = self.client.get("/admin/orders/order/", {"q": "Ромашка"})
        self.assertContains(response, "Z-7")

    def test_create_order_through_admin_form(self):
        """Менеджер создаёт заказ с одним товаром -> появляются подэтапы, этап и бюджет."""
        data = {
            "number": "ADM-1", "client": self.client_obj.pk, "manager": self.user.pk,
            "order_type": self.order_type.pk,
            "deadline_plan": (timezone.localdate() + timedelta(days=20)).isoformat(),
            "contract_number": "",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.product.pk, "items-0-quantity": "10",
            "items-0-markup_percent": "30.00", "items-0-price": "0", "items-0-variant": "белая, M",
        }
        response = self.client.post("/admin/orders/order/add/", data)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        order = Order.objects.get(number="ADM-1")
        self.assertEqual(order.substages.count(), 2)
        self.assertEqual(order.current_stage, self.stage1)
        self.assertEqual(BudgetItem.objects.filter(order=order).count(), 1)
        self.assertEqual(order.contract_amount_calculated, Decimal("1300.00"))
