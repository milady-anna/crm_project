from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from orders.models import Order, OrderItem, OrderType
from partners.models import Client
from products.models import OurProduct


class OrderListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("manager", password="pw")
        cls.client_obj = Client.objects.create(name="ООО Ромашка")
        otype = OrderType.objects.create(name="Россия")
        cls.order = Order.objects.create(
            number="A-1", client=cls.client_obj, manager=cls.user, order_type=otype,
            deadline_plan=timezone.localdate() + timedelta(days=5),
        )
        pen = OurProduct.objects.create(name="Ручка")
        OrderItem.objects.create(order=cls.order, product=pen, quantity=5, price=Decimal("250.00"))

    def test_login_required(self):
        response = self.client.get(reverse("dashboard:order_list"))
        self.assertEqual(response.status_code, 302)

    def test_list_shows_real_amount(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:order_list"))
        self.assertContains(response, "A-1")
        self.assertContains(response, "1250")

    def test_search_by_client_name_and_number(self):
        self.client.force_login(self.user)
        url = reverse("dashboard:order_list")
        self.assertContains(self.client.get(url, {"search": "Ромашка"}), "A-1")
        self.assertContains(self.client.get(url, {"search": "A-1"}), "A-1")
        self.assertNotContains(self.client.get(url, {"search": "нет такого"}), "A-1")

    def test_root_redirects_to_list(self):
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("dashboard:order_list"))
