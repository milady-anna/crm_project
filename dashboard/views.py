# dashboard/views.py
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.views.generic import ListView

from orders.models import Order, Stage
from partners.models import Client, Contractor
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.views import View
from orders.models import Substage, OrderComment


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "dashboard/order_list.html"
    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        queryset = Order.objects.select_related(
            "client", "manager", "current_stage", "order_type"
        ).prefetch_related("items", "substages")

        # По умолчанию скрываем завершённые
        show_completed = self.request.GET.get("show_completed", "")
        if show_completed != "1":
            completed_ids = [o.pk for o in Order.objects.all() if o.is_completed]
            queryset = queryset.exclude(pk__in=completed_ids)

        # Поиск по номеру или клиенту
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(number__icontains=search_query)
                | Q(client__name__icontains=search_query)
            )

        # Фильтр по этапу
        stage_id = self.request.GET.get("stage", "")
        if stage_id.isdigit():
            queryset = queryset.filter(current_stage_id=stage_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stages"] = Stage.objects.all()
        context["show_completed"] = self.request.GET.get("show_completed", "")

        # Сортировка по ближайшему дедлайну в Python
        orders = list(context["orders"])
        orders.sort(key=lambda o: o.nearest_deadline)
        context["orders"] = orders

        return context


class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = "dashboard/client_list.html"
    context_object_name = "clients"
    paginate_by = 20

    def get_queryset(self):
        queryset = Client.objects.all().order_by("name")

        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        status = self.request.GET.get("status", "")
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Client.STATUS_CHOICES
        return context


class ContractorListView(LoginRequiredMixin, ListView):
    model = Contractor
    template_name = "dashboard/contractor_list.html"
    context_object_name = "contractors"
    paginate_by = 20

    def get_queryset(self):
        queryset = Contractor.objects.all().order_by("name")

        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        product_search = self.request.GET.get("product", "").strip()
        if product_search:
            queryset = queryset.filter(
                supplierproduct__name__icontains=product_search
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product_search"] = self.request.GET.get("product", "").strip()
        return context


class OrderDetailView(LoginRequiredMixin, View):
    """Детальная страница заказа"""

    template_name = "dashboard/order_detail.html"

    def get(self, request, pk):
        order = get_object_or_404(
            Order.objects.select_related(
                "client", "manager", "current_stage", "order_type"
            ).prefetch_related(
                "items",
                "items__product",
                "items__components",
                "items__components__supplier_product",  # <-- ИСПРАВЛЕНО
                "substages",
                "substages__template",
                "substages__template__template_documents",
                "substages__template__template_documents__document_template",  # <-- ИСПРАВЛЕНО
                "comments",
                "comments__author",
            ),
            pk=pk,
        )
        from finance.models import BudgetItem
        from partners.models import Contractor

        # Получаем активный этап из GET-параметра, по умолчанию — текущий этап заказа
        active_stage_id = request.GET.get("stage")
        active_stage = None
        if active_stage_id and active_stage_id.isdigit():
            active_stage = get_object_or_404(Stage, pk=active_stage_id)
        elif order.current_stage:
            active_stage = order.current_stage

        # Подэтапы только для активного этапа
        if active_stage:
            filtered_substages = order.substages.filter(stage=active_stage).order_by(
                "index_in_stage"
            )
        else:
            filtered_substages = order.substages.all().order_by(
                "stage__order_index", "index_in_stage"
            )

        context = {
            "order": order,
            "comments": order.comments.select_related("author").order_by("-created_at"),
            "budget_items": BudgetItem.objects.filter(
                order=order, flow_type="expense"
            ).select_related("contractor"),
            "contractors": Contractor.objects.all(),
            "stages": Stage.objects.all().order_by("order_index"),
            "active_stage": active_stage,
            "substages": filtered_substages,
            "today": timezone.localdate(),
        }
        from django.shortcuts import render

        return render(request, self.template_name, context)


class UpdateSubstageStatusView(LoginRequiredMixin, View):
    """AJAX: смена статуса подэтапа"""

    def post(self, request, pk, substage_pk):
        substage = get_object_or_404(Substage, pk=substage_pk, order_id=pk)
        new_status = request.POST.get("status")
        if new_status in ["not_started", "in_progress", "completed"]:
            substage.status = new_status
            from django.utils import timezone

            if new_status == "completed":
                substage.completed_date = timezone.localdate()
            else:
                substage.completed_date = None
            substage.save()

            # Пересчёт прогресса заказа
            substage.order.update_current_stage()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"status": "ok", "new_status": new_status})
        return redirect("dashboard:order_detail", pk=pk)


class AddCommentView(LoginRequiredMixin, View):
    """Добавление комментария к заказу"""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        text = request.POST.get("text", "").strip()
        if text:
            OrderComment.objects.create(order=order, author=request.user, text=text)
        return redirect("dashboard:order_detail", pk=pk)


class AddBudgetItemView(LoginRequiredMixin, View):
    """Добавление платежа в бюджет заказа"""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        description = request.POST.get("description", "").strip()
        contractor_id = request.POST.get("contractor")
        amount = request.POST.get("amount", 0)
        planned_date = request.POST.get("planned_date")

        if description and amount:
            BudgetItem.objects.create(
                order=order,
                description=description,
                contractor_id=contractor_id if contractor_id else None,
                amount_plan=amount,
                planned_date=planned_date if planned_date else None,
                flow_type="expense",
            )
        return redirect("dashboard:order_detail", pk=pk)


class ClientDetailView(LoginRequiredMixin, View):
    """Детальная страница клиента"""

    template_name = "dashboard/client_detail.html"

    def get(self, request, pk):
        client = get_object_or_404(
            Client.objects.prefetch_related(
                "order_set",  # <-- было "orders"
                "order_set__items",  # <-- было "orders__items"
                "order_set__items__product",  # <-- было "orders__items__product"
                "order_set__substages",  # <-- было "orders__substages"
                "order_set__comments",  # <-- было "orders__comments"
                "order_set__comments__author",  # <-- было "orders__comments__author"
            ),
            pk=pk,
        )

        # Все заказы клиента
        orders = client.order_set.all().order_by("-created_at")

        # Все комментарии по всем заказам клиента
        from orders.models import OrderComment

        comments = (
            OrderComment.objects.filter(order__client=client)
            .select_related("author", "order")
            .order_by("-created_at")
        )

        # Статистика
        total_orders = orders.count()
        total_amount = sum(
            (order.contract_amount_calculated for order in orders), Decimal("0")
        )
        active_orders = orders.exclude(
            pk__in=[o.pk for o in orders if o.is_completed]
        ).count()

        context = {
            "client": client,
            "orders": orders,
            "comments": comments,
            "total_orders": total_orders,
            "total_amount": total_amount,
            "active_orders": active_orders,
            "today": timezone.localdate(),
        }
        from django.shortcuts import render

        return render(request, self.template_name, context)


class ContractorDetailView(LoginRequiredMixin, View):
    """Детальная страница подрядчика"""

    template_name = "dashboard/contractor_detail.html"

    def get(self, request, pk):
        from orders.models import Order
        from finance.models import BudgetItem
        from partners.models import ContractorReview

        contractor = get_object_or_404(
            Contractor.objects.prefetch_related(
                "supplierproduct_set",
            ),
            pk=pk,
        )

        # Заказы с этим подрядчиком (через BudgetItem)
        orders_with_contractor = (
            BudgetItem.objects.filter(contractor=contractor)
            .select_related("order", "order__client")
            .order_by("-order__created_at")
        )

        # Заказы, где использовались товары этого подрядчика
        supplier_product_ids = contractor.supplierproduct_set.values_list(
            "pk", flat=True
        )
        contractor_orders = (
            Order.objects.filter(
                items__components__supplier_product_id__in=supplier_product_ids
            )
            .distinct()
            .order_by("-created_at")
        )

        # Отзывы
        reviews = (
            ContractorReview.objects.filter(contractor=contractor)
            .select_related("order", "order__client")
            .order_by("-created_at")
        )

        context = {
            "contractor": contractor,
            "products": contractor.supplierproduct_set.all(),
            "orders_with_contractor": orders_with_contractor,
            "reviews": reviews,
            "contractor_orders": contractor_orders,
        }
        from django.shortcuts import render

        return render(request, self.template_name, context)


class AddContractorReviewView(LoginRequiredMixin, View):
    """Добавление отзыва/оценки подрядчику"""

    def post(self, request, pk):
        contractor = get_object_or_404(Contractor, pk=pk)
        rating = request.POST.get("rating", 0)
        comment = request.POST.get("comment", "").strip()
        order_id = request.POST.get("order")

        if rating and comment:
            from partners.models import ContractorReview

            review = ContractorReview(
                contractor=contractor, rating=int(rating), comment=comment
            )
            if order_id and order_id.isdigit():
                from orders.models import Order

                review.order_id = order_id
            review.save()
        return redirect("dashboard:contractor_detail", pk=pk)
