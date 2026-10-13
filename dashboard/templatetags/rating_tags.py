from django import template

register = template.Library()


@register.filter(name="rating_color")
def rating_color(value):
    """
    Возвращает цвет для рейтинга:
    1-2 = красный, 3 = жёлтый, 4 = светло-зелёный, 5 = зелёный
    """
    try:
        rating = float(value)
    except (ValueError, TypeError):
        return "#adb5bd"  # серый по умолчанию

    if rating <= 0:
        return "#adb5bd"

    # Цвета для разных уровней рейтинга
    if rating <= 2:
        return "#dc3545"  # красный
    elif rating <= 3:
        return "#ffc107"  # жёлтый
    elif rating <= 4:
        return "#8bc34a"  # светло-зелёный
    else:
        return "#4caf50"  # зелёный


@register.filter(name="deadline_color")
def deadline_color(value):
    """
    Возвращает цвет для вертикальной полоски:
    - Просрочено = красный
    - Менее 3 дней = оранжевый
    - Менее 7 дней = жёлтый
    - Более 7 дней = зелёный
    """
    from django.utils import timezone

    try:
        today = timezone.localdate()
        days_left = (value - today).days

        if days_left < 0:
            return "#dc3545"  # красный (просрочено)
        elif days_left <= 3:
            return "#fd7e14"  # оранжевый (критично)
        elif days_left <= 7:
            return "#ffc107"  # жёлтый (внимание)
        else:
            return "#28a745"  # зелёный (норма)
    except:
        return "#6c757d"  # серый по умолчанию


@register.filter(name="multiply")
def multiply(value, arg):
    """Перемножает числа (для суммы компонента: кол-во × цена)."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ""
