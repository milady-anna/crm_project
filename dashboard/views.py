# dashboard/views.py
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.views.generic import ListView

from orders.models import Order, Stage, OrderType
from partners.models import Client, Contractor
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.views import View
from orders.models import Substage, OrderComment


def user_is_manager(user):
    """Рядовой менеджер (не руководитель и не администратор)."""
    return user.is_authenticated and not (user.is_staff or user.is_superuser)


def order_scope(request):
    """Заказы, видимые текущему пользователю.

    Руководитель/admin видит всё, менеджер — только свои заказы.
    """
    qs = Order.objects.select_related(
        "client", "manager", "current_stage", "order_type"
    ).prefetch_related("items", "substages")
    if user_is_manager(request.user):
        qs = qs.filter(manager=request.user)
    return qs


def check_order_access(request, order):
    """Запрещает менеджеру открывать/менять чужой заказ (защита от IDOR)."""
    if user_is_manager(request.user) and order.manager_id != request.user.pk:
        raise PermissionDenied


def parse_amount(raw):
    """Безопасно превращает строку формы в Decimal; None — если не число."""
    try:
        return Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "dashboard/order_list.html"
    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        queryset = order_scope(self.request)

        # По умолчанию скрываем завершённые
        show_completed = self.request.GET.get("show_completed", "")
        if show_completed != "1":
            completed_ids = [o.pk for o in queryset if o.is_completed]
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
                "items__components__supplier_product",
                "substages",
                "substages__template",
                "substages__template__template_documents",
                "substages__template__template_documents__document_template",
                "comments",
                "comments__author",
            ),
            pk=pk,
        )
        check_order_access(request, order)
        from finance.models import BudgetItem
        from partners.models import Contractor
        from products.models import OurProduct

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

        # Фактические платежи заказа + уже созданные из них (для кнопки «Добавить платёж»)
        transactions = (
            order.transactions.select_related("budget_item__contractor", "budget_item")
            .order_by("-date_fact", "-created_at")
        )
        paid_total = sum(
            (t.amount_fact for t in transactions if t.status == "paid"), Decimal("0")
        )
        pending_total = sum(
            (t.amount_fact for t in transactions if t.status == "pending"), Decimal("0")
        )
        budget_items_with_tx = set(
            tx.budget_item_id for tx in transactions if tx.budget_item_id
        )
        free_budget_items = [
            bi
            for bi in BudgetItem.objects.filter(order=order, flow_type="expense")
            .select_related("contractor")
            .order_by("component_name")
            if bi.pk not in budget_items_with_tx
        ]

        context = {
            "order": order,
            "comments": order.comments.select_related("author").order_by("-created_at"),
            "budget_items": BudgetItem.objects.filter(
                order=order, flow_type="expense"
            ).select_related("contractor"),
            "transactions": transactions,
            "paid_total": paid_total,
            "pending_total": pending_total,
            "free_budget_items": free_budget_items,
            "contractors": Contractor.objects.all(),
            "our_products": OurProduct.objects.all().order_by("name"),
            "stages": Stage.objects.all().order_by("order_index"),
            "active_stage": active_stage,
            "substages": filtered_substages,
            "today": timezone.localdate(),
        }
        from django.shortcuts import render

        return render(request, self.template_name, context)


class UpdateSubstageStatusView(LoginRequiredMixin, View):
    """AJAX/POST: смена статуса подэтапа."""

    def post(self, request, pk, substage_pk):
        order = get_object_or_404(Order, pk=pk)
        check_order_access(request, order)
        substage = get_object_or_404(Substage, pk=substage_pk, order=order)
        new_status = request.POST.get("status")
        if new_status in ["not_started", "in_progress", "completed"]:
            substage.status = new_status
            if new_status == "completed":
                substage.completed_date = timezone.localdate()
            else:
                substage.completed_date = None
            substage.save()  # внутри save() уже пересчитывается этап заказа

            wants_json = (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or "application/json" in request.headers.get("Accept", "")
            )
            if wants_json:
                return JsonResponse(
                    {
                        "status": "ok",
                        "new_status": new_status,
                        "progress_percent": substage.order.progress_percent,
                        "is_completed": substage.order.is_completed,
                    }
                )
        messages.error(request, "Некорректный статус подэтапа.")
        return redirect("dashboard:order_detail", pk=pk)


class AddCommentView(LoginRequiredMixin, View):
    """Добавление комментария к заказу"""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        check_order_access(request, order)
        text = request.POST.get("text", "").strip()
        if text:
            OrderComment.objects.create(order=order, author=request.user, text=text)
        else:
            messages.error(request, "Комментарий не может быть пустым.")
        return redirect("dashboard:order_detail", pk=pk)


class AddBudgetItemView(LoginRequiredMixin, View):
    """Добавление платежа в бюджет заказа"""

    def post(self, request, pk):
        from finance.models import BudgetItem

        order = get_object_or_404(Order, pk=pk)
        check_order_access(request, order)
        description = request.POST.get("description", "").strip()
        contractor_id = request.POST.get("contractor")
        amount = parse_amount(request.POST.get("amount"))
        planned_date_raw = request.POST.get("planned_date", "").strip()

        planned_date = None
        if planned_date_raw:
            try:
                planned_date = date.fromisoformat(planned_date_raw)
            except ValueError:
                messages.error(request, "Некорректная дата платежа.")
                return redirect("dashboard:order_detail", pk=pk)

        errors = []
        if not description:
            errors.append("Укажите назначение платежа.")
        if amount is None or amount <= 0:
            errors.append("Сумма должна быть положительным числом.")
        if contractor_id:
            if not Contractor.objects.filter(pk=contractor_id).exists():
                errors.append("Подрядчик не найден.")
        else:
            contractor_id = None

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("dashboard:order_detail", pk=pk)

        BudgetItem.objects.create(
            order=order,
            component_name=description,
            contractor_id=contractor_id,
            amount_plan=amount,
            date_plan=planned_date,
            flow_type="expense",
        )
        messages.success(request, "Платёж добавлен в бюджет заказа.")
        return redirect("dashboard:order_detail", pk=pk)


class UpdateOrderItemView(LoginRequiredMixin, View):
    """POST: редактирование позиции заказа прямо в таблице (расчёт цены по договору).

    Все пользователи системы могут менять: количество, цену подрядчика,
    наценку %, налог % и итоговую цену за единицу.
    """

    def post(self, request, pk):
        from orders.models import OrderItem

        item = get_object_or_404(OrderItem.objects.select_related("order"), pk=pk)
        check_order_access(request, item.order)

        errors = []
        updates = {}

        def dec_field(name, label, max_value=None, allow_empty=False):
            raw = request.POST.get(name)
            if raw is None:
                return None
            value = parse_amount(raw)
            if value is None and not (allow_empty and raw.strip() == ""):
                errors.append(f"«{label}» — не число.")
                return None
            if value is not None and value < 0:
                errors.append(f"«{label}» не может быть отрицательной.")
                return None
            if max_value is not None and value is not None and value > max_value:
                errors.append(f"«{label}» слишком большая (максимум {max_value}).")
                return None
            return value

        # Количество
        qty_raw = dec_field("quantity", "Количество", max_value=100000)
        if qty_raw is not None:
            if qty_raw != int(qty_raw) or qty_raw < 1:
                errors.append("Количество должно быть целым числом от 1.")
            else:
                updates["quantity"] = int(qty_raw)

        # Цена подрядчика: пустое поле = сброс ручной цены (снова считаем по компонентам)
        cost_raw = request.POST.get("contractor_cost")
        if cost_raw is not None:
            if cost_raw.strip() == "":
                updates["manual_cost"] = None
            else:
                value = dec_field("contractor_cost", "Цена подрядчика", max_value=9999999)
                if value is not None:
                    updates["manual_cost"] = value

        markup = dec_field("markup_percent", "Наценка, %", max_value=999.99)
        if markup is not None:
            updates["markup_percent"] = markup

        tax = dec_field("tax_rate", "Налог, %", max_value=99.99)
        if tax is not None:
            updates["tax_rate"] = tax

        price = dec_field("price", "Итоговая цена", max_value=9999999)
        if price is not None:
            updates["price"] = price

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("dashboard:order_detail", pk=item.order_id)

        manual_price_given = "price" in updates
        explicit_fields = [f for f in ("markup_percent", "tax_rate") if f in updates]

        for field, value in updates.items():
            setattr(item, field, value)

        if manual_price_given:
            # Менеджер задал итог руками — пересчёт из себестоимости НЕ делаем,
            # но обратную наценку показывем честно (поле markup_percent не трогаем).
            save_fields = ["price"] + explicit_fields
            if "quantity" in updates:
                save_fields.append("quantity")
            if "manual_cost" in updates:
                save_fields.append("manual_cost")
            item.save(update_fields=save_fields)
        else:
            item.save()  # внутри save() произойдёт recalculate(): цена = подрядчик × (1+наценка)

        messages.success(request, f"Позиция «{item.product.name}» пересчитана.")
        return redirect("dashboard:order_detail", pk=item.order_id)


class AddOrderItemView(LoginRequiredMixin, View):
    """POST: добавить товар в заказ (выбор из каталога наших товаров)."""

    def post(self, request, pk):
        from orders.models import Order, OrderItem
        from products.models import OurProduct

        order = get_object_or_404(Order, pk=pk)
        check_order_access(request, order)

        product_id = request.POST.get("product")
        quantity = parse_amount(request.POST.get("quantity"))
        markup = parse_amount(request.POST.get("markup_percent"))

        errors = []
        product = (
            OurProduct.objects.filter(pk=product_id).first()
            if product_id and product_id.isdigit()
            else None
        )
        if not product:
            errors.append("Выберите товар из каталога.")
        if quantity is None or quantity < 1 or quantity != int(quantity):
            errors.append("Количество должно быть целым числом от 1.")
        if markup is not None and (markup < 0 or markup > 999):
            errors.append("Наценка должна быть от 0 до 999%.")
            markup = None

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("dashboard:order_detail", pk=pk)

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=int(quantity),
            **({"markup_percent": markup} if markup is not None else {}),
        )
        messages.success(request, f"Товар «{product.name}» добавлен в заказ.")
        return redirect("dashboard:order_detail", pk=pk)


class DeleteOrderItemView(LoginRequiredMixin, View):
    """POST: удалить позицию из заказа."""

    def post(self, request, pk):
        from orders.models import OrderItem

        item = get_object_or_404(OrderItem.objects.select_related("order"), pk=pk)
        check_order_access(request, item.order)
        order_id = item.order_id
        name = item.product.name
        item.delete()
        messages.success(request, f"Позиция «{name}» удалена из заказа.")
        return redirect("dashboard:order_detail", pk=order_id)


class UpdateOrderDocumentsView(LoginRequiredMixin, View):
    """POST: прикрепить файлы документов к заказу (КП, договор) и/или ссылки."""

    ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "jpeg", "zip"}
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ

    def _clean_file(self, fobj, label):
        """Возвращает (файл, ошибка). Проверяет размер и расширение."""
        import os

        ext = os.path.splitext(fobj.name)[1].lower().lstrip(".")
        if ext not in self.ALLOWED_EXT:
            return None, f"Файл «{label}»: недопустимый тип .{ext}."
        if fobj.size > self.MAX_FILE_SIZE:
            return None, f"Файл «{label}»: больше 20 МБ."
        return fobj, None

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        check_order_access(request, order)

        errors = []
        updated = []

        for field, label in (("kp_file", "КП"), ("contract_file", "Договор")):
            fobj = request.FILES.get(field)
            if fobj:
                cleaned, error = self._clean_file(fobj, label)
                if error:
                    errors.append(error)
                else:
                    setattr(order, field, cleaned)
                    updated.append(label)

        for field, label in (("contract_url", "ссылка на договор"), ("kp_url", "ссылка на КП")):
            raw = request.POST.get(field)
            if raw is not None and raw.strip():
                value = raw.strip()
                if not value.startswith(("http://", "https://")):
                    errors.append(f"«{label}» должна начинаться с http(s)://.")
                else:
                    setattr(order, field, value[:500])
                    updated.append(label)

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("dashboard:order_detail", pk=pk)

        if updated:
            order.save(update_fields=["contract_file", "kp_file", "contract_url", "kp_url"])
            messages.success(request, "Документы обновлены: " + ", ".join(updated) + ".")
        else:
            messages.error(request, "Не выбран ни файл, ни ссылка для загрузки.")
        return redirect("dashboard:order_detail", pk=pk)


class UpdateBudgetItemView(LoginRequiredMixin, View):
    """POST: inline-редактирование планового платежа в бюджете заказа."""

    def post(self, request, pk):
        from finance.models import BudgetItem

        item = get_object_or_404(BudgetItem.objects.select_related("order"), pk=pk)
        check_order_access(request, item.order)

        field = request.POST.get("field")
        value = request.POST.get("value", "")

        if field == "description":
            if not value.strip():
                messages.error(request, "Назначение платежа не может быть пустым.")
            else:
                item.component_name = value.strip()[:200]
                item.save(update_fields=["component_name"])
        elif field == "contractor":
            if value and not Contractor.objects.filter(pk=value).exists():
                messages.error(request, "Подрядчик не найден.")
            else:
                item.contractor_id = value or None
                item.save(update_fields=["contractor"])
        elif field == "amount":
            amount = parse_amount(value)
            if amount is None or amount <= 0:
                messages.error(request, "Сумма должна быть положительным числом.")
            else:
                item.amount_plan = amount
                item.save(update_fields=["amount_plan"])
        else:
            messages.error(request, "Неизвестное поле платежа.")

        return JsonResponse({"status": "ok"})


class AddTransactionView(LoginRequiredMixin, View):
    """POST: добавить фактический платёж по заказу.

    Платёж можно создать «с нуля» (своя сумма/назначение) или подтянуть
    из статьи бюджета — тогда сумма и подрядчик берутся из статьи, а
    Transaction привязывается к ней (статья сама посчитает оплату).
    """

    def post(self, request, pk):
        from finance.models import BudgetItem, Transaction

        order = get_object_or_404(Order, pk=pk)
        check_order_access(request, order)

        budget_item = None
        bi_id = request.POST.get("budget_item")
        if bi_id and bi_id.isdigit():
            budget_item = BudgetItem.objects.filter(pk=bi_id, order=order).first()

        description = request.POST.get("description", "").strip()
        contractor_id = request.POST.get("contractor")
        amount = parse_amount(request.POST.get("amount"))
        flow_type = request.POST.get("flow_type", "expense")
        status = request.POST.get("status", "pending")
        date_raw = request.POST.get("date_fact", "").strip()

        if budget_item:
            amount = amount or budget_item.amount_plan
            description = description or budget_item.component_name
            if not contractor_id and budget_item.contractor_id:
                contractor_id = str(budget_item.contractor_id)

        errors = []
        if not description:
            errors.append("Укажите назначение платежа.")
        if amount is None or amount <= Decimal("0"):
            errors.append("Сумма должна быть положительным числом.")
        elif amount > Decimal("9999999999"):
            errors.append("Сумма слишком большая.")
        if flow_type not in ("income", "expense"):
            flow_type = "expense"
        if status not in ("pending", "paid"):
            status = "pending"
        if contractor_id and not Contractor.objects.filter(pk=contractor_id).exists():
            errors.append("Подрядчик не найден.")

        planned_date = None
        if date_raw:
            try:
                planned_date = date.fromisoformat(date_raw)
            except ValueError:
                errors.append("Некорректная дата платежа.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("dashboard:order_detail", pk=pk)

        Transaction.objects.create(
            order=order,
            budget_item=budget_item,
            flow_type=flow_type,
            amount_fact=amount,
            date_fact=planned_date,
            status=status,
            comment=description[:500],
        )
        messages.success(request, f"Платёж «{description}» на {amount} ₽ добавлен.")
        return redirect("dashboard:order_detail", pk=pk)


class DeleteTransactionView(LoginRequiredMixin, View):
    """POST: удалить ошибочный фактический платёж."""

    def post(self, request, pk):
        from finance.models import Transaction

        tx = get_object_or_404(
            Transaction.objects.select_related("order"), pk=pk, order__pk=request.POST.get("order_pk")
        )
        order_pk = tx.order_id
        check_order_access(request, tx.order)
        tx.delete()
        messages.success(request, "Платёж удалён.")
        return redirect("dashboard:order_detail", pk=order_pk)


class OrderCreateView(LoginRequiredMixin, View):
    """Страница создания заказа (форма). Все пользователи системы могут создавать."""

    template_name = "dashboard/order_form.html"

    def _form_context(self, request, data=None, errors=None):
        from products.models import OurProduct  # noqa: F401 (единый импорт контекста)

        return {
            "clients": Client.objects.order_by("name"),
            "order_types": OrderType.objects.order_by("name"),
            "stages": Stage.objects.order_by("order_index"),
            "today": timezone.localdate(),
            "data": data or {},
            "errors": errors or {},
        }

    def get(self, request):
        from django.shortcuts import render

        default_data = {"deadline_plan": (timezone.localdate() + timedelta(days=30)).isoformat()}
        return render(request, self.template_name, self._form_context(request, default_data))

    def post(self, request):
        from django.shortcuts import render
        from orders.services import sync_order

        data = {k: request.POST.get(k, "").strip() for k in (
            "number", "client", "order_type", "manager", "deadline_plan",
            "contract_number", "prepayment_percent", "brandbook_url",
            "kp_url", "contract_url",
        )}
        errors = {}

        # Номер заказа
        number = data["number"]
        if not number:
            errors["number"] = "Укажите номер заказа."
        elif Order.objects.filter(number=number).exists():
            errors["number"] = "Заказ с таким номером уже существует."

        # Заказчик
        client = None
        if data["client"].isdigit():
            client = Client.objects.filter(pk=data["client"]).first()
        if not client:
            errors["client"] = "Выберите заказчика."

        # Тип заказа
        order_type = None
        if data["order_type"].isdigit():
            order_type = OrderType.objects.filter(pk=data["order_type"]).first()
        if not order_type:
            errors["order_type"] = "Выберите тип заказа (он создаст подэтапы)."

        # Менеджер
        manager = None
        if data["manager"].isdigit():
            manager = User.objects.filter(pk=data["manager"]).first()
        if not manager:
            if user_is_manager(request.user):
                manager = request.user
            else:
                manager = request.user

        # Дедлайн
        deadline_plan = None
        if data["deadline_plan"]:
            try:
                deadline_plan = date.fromisoformat(data["deadline_plan"])
            except ValueError:
                errors["deadline_plan"] = "Некорректная дата."
        else:
            errors["deadline_plan"] = "Укажите плановый дедлайн."

        # Предоплата
        prepayment = parse_amount(data["prepayment_percent"] or "0")
        if prepayment is None or prepayment < 0 or prepayment > 100:
            errors["prepayment_percent"] = "Процент предоплаты — число от 0 до 100."
            prepayment = Decimal("0")

        for url_field, label in (("brandbook_url", "брендбук"), ("kp_url", "КП"), ("contract_url", "договор")):
            raw = data[url_field]
            if raw and not raw.startswith(("http://", "https://")):
                errors[url_field] = f"Ссылка на {label} должна начинаться с http(s)://"

        if errors:
            messages.error(request, "Исправьте ошибки в форме.")
            return render(request, self.template_name, self._form_context(request, data, errors))

        order = Order(
            number=number,
            client=client,
            order_type=order_type,
            manager=manager,
            deadline_plan=deadline_plan,
            contract_number=data["contract_number"],
            prepayment_percent=prepayment,
            brandbook_url=data["brandbook_url"][:500],
            kp_url=data["kp_url"][:500],
            contract_url=data["contract_url"][:500],
        )
        order.save()  # внутри создадутся подэтапы из шаблона типа заказа
        sync_order(order, created=False)
        messages.success(
            request, f"Заказ #{order.number} создан, подэтапы простроены из шаблона."
        )
        return redirect("dashboard:order_detail", pk=order.pk)


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
        orders_with_contractor_products = (
            Order.objects.filter(
                items__components__supplier_product_id__in=supplier_product_ids
            )
            .distinct()
            .select_related("client", "manager", "current_stage")
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
            "contractor_orders": orders_with_contractor_products,
        }
        from django.shortcuts import render

        return render(request, self.template_name, context)


class AddContractorReviewView(LoginRequiredMixin, View):
    """Добавление отзыва/оценки подрядчику"""

    def post(self, request, pk):
        contractor = get_object_or_404(Contractor, pk=pk)
        rating_raw = request.POST.get("rating", "")
        comment = request.POST.get("comment", "").strip()
        order_id = request.POST.get("order")

        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            rating = None

        if rating is None or not 1 <= rating <= 5:
            messages.error(request, "Оценка должна быть от 1 до 5.")
            return redirect("dashboard:contractor_detail", pk=pk)
        if not comment:
            messages.error(request, "Добавьте комментарий к оценке.")
            return redirect("dashboard:contractor_detail", pk=pk)

        from partners.models import ContractorReview

        review = ContractorReview(
            contractor=contractor, rating=rating, comment=comment
        )
        if order_id and order_id.isdigit():
            from orders.models import Order

            order = Order.objects.filter(pk=order_id).first()
            if order:
                check_order_access(request, order)
                review.order = order
        review.save()
        messages.success(request, "Оценка подрядчика сохранена.")
        return redirect("dashboard:contractor_detail", pk=pk)
