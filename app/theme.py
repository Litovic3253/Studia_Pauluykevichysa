"""Единый визуальный язык приложения: тема Material 3, карточная вёрстка,
адаптивная сетка и общие элементы (шапка экрана, секция, «таблетки» статусов)."""
from typing import Iterable

import flet as ft

ACCENT_COLOR = "#3D5AFE"

CARD_RADIUS = 16
BUTTON_RADIUS = 12
SPACING = 16
PAGE_PADDING = 24
FIELD_RADIUS = 10

# Ширина контента на больших мониторах — дальше строки становятся нечитаемо длинными.
MAX_CONTENT_WIDTH = 1180
# Ниже этой ширины окна: меню только иконками, «Клиенты» — список ИЛИ карточка.
COMPACT_WIDTH = 900
# От этой ширины окна меню показывает подписи рядом с иконками.
WIDE_WIDTH = 1280

# Статус → (подпись без эмодзи, цвет «таблетки»).
STATUS_STYLES = {
    "new": ("Новый", ft.Colors.BLUE),
    "queued": ("В очереди", ft.Colors.AMBER_800),
    "printing": ("Печатается", ft.Colors.DEEP_PURPLE),
    "post": ("Постобработка", ft.Colors.ORANGE_800),
    "ready": ("Готов", ft.Colors.GREEN),
    "delivered": ("Выдан", ft.Colors.BLUE_GREY),
    "cancelled": ("Отменён", ft.Colors.RED),
}


def _button_shape() -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=BUTTON_RADIUS)


def _rounded_button_themes() -> dict:
    """Общие скруглённые темы кнопок — применяются и к светлой, и к тёмной теме,
    чтобы BUTTON_RADIUS действовал на все ElevatedButton/OutlinedButton/TextButton/IconButton
    без изменений в экранах."""
    return dict(
        elevated_button_theme=ft.ElevatedButtonTheme(shape=_button_shape()),
        outlined_button_theme=ft.OutlinedButtonTheme(shape=_button_shape()),
        text_button_theme=ft.TextButtonTheme(shape=_button_shape()),
        filled_button_theme=ft.FilledButtonTheme(shape=_button_shape()),
        icon_button_theme=ft.IconButtonTheme(shape=_button_shape()),
    )


LIGHT_THEME = ft.Theme(color_scheme_seed=ACCENT_COLOR, use_material3=True, **_rounded_button_themes())
DARK_THEME = ft.Theme(color_scheme_seed=ACCENT_COLOR, use_material3=True, **_rounded_button_themes())

THEME_MODE_CYCLE = ["system", "light", "dark"]

FLET_THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}

THEME_ICONS = {
    "system": ft.Icons.BRIGHTNESS_AUTO,
    "light": ft.Icons.LIGHT_MODE,
    "dark": ft.Icons.DARK_MODE,
}


def next_theme_mode(current: str) -> str:
    """Следующее значение в цикле система → светлая → тёмная → снова система."""
    try:
        idx = THEME_MODE_CYCLE.index(current)
    except ValueError:
        idx = -1
    return THEME_MODE_CYCLE[(idx + 1) % len(THEME_MODE_CYCLE)]


def flet_theme_mode(value: str) -> ft.ThemeMode:
    """Безопасное преобразование строки в ft.ThemeMode — неизвестное значение считается «system»."""
    return FLET_THEME_MODES.get(value, ft.ThemeMode.SYSTEM)


def card(content: ft.Control, **container_kwargs) -> ft.Container:
    """Единая обёртка «карточка»: скруглённые углы, поверхностный фон темы,
    внутренний отступ — используется всеми экранами вместо голого Column/Row."""
    defaults = dict(
        content=content,
        padding=SPACING,
        border_radius=CARD_RADIUS,
        bgcolor=ft.Colors.SURFACE,
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
        shadow=ft.BoxShadow(
            blur_radius=8,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
    )
    defaults.update(container_kwargs)
    return ft.Container(**defaults)


# ---------- адаптивная раскладка ----------

def content_padding(width: float) -> float:
    """Горизонтальный отступ контента: на широком окне центрирует колонку MAX_CONTENT_WIDTH."""
    return max(PAGE_PADDING, (width - MAX_CONTENT_WIDTH) / 2)


def grid(controls: Iterable[ft.Control], **kwargs) -> ft.ResponsiveRow:
    """Адаптивная сетка: у каждого контрола свой col (напр. {"xs": 12, "md": 6, "lg": 4}).
    Выравнивание по верху — чтобы поле с подсказкой снизу не сдвигало соседей."""
    defaults = dict(spacing=SPACING, run_spacing=SPACING, vertical_alignment=ft.CrossAxisAlignment.START)
    defaults.update(kwargs)
    return ft.ResponsiveRow(list(controls), **defaults)


def dropdown(label: str, width: int = 240, **kwargs) -> ft.Dropdown:
    """Выпадающий список в едином стиле. В Flet 0.27 Dropdown (M3 DropdownMenu) не растягивается
    по колонке, а без ширины сжимается по содержимому («Мате / риал») — поэтому ширина фиксированная."""
    defaults = dict(label=label, border_radius=FIELD_RADIUS, width=width)
    defaults.update(kwargs)
    return ft.Dropdown(**defaults)


def in_col(control: ft.Control, col) -> ft.Row:
    """Обёртка для контролов, которые сами не растягиваются по колонке ResponsiveRow (Dropdown)."""
    return ft.Row([control], col=col)


def field(label: str, col=None, **kwargs) -> ft.TextField:
    """Текстовое поле в едином стиле."""
    defaults = dict(label=label, border_radius=FIELD_RADIUS, col=col or {"xs": 12, "md": 6})
    defaults.update(kwargs)
    return ft.TextField(**defaults)


# ---------- общие элементы экранов ----------

def page_header(title: str, subtitle: str | None = None, actions: list[ft.Control] | None = None,
                leading: ft.Control | None = None) -> ft.Control:
    """Шапка экрана: заголовок + подзаголовок слева, действия справа (на узком окне — под заголовком)."""
    title_col = ft.Column(
        [ft.Text(title, size=24, weight=ft.FontWeight.W_700)]
        + ([ft.Text(subtitle, size=13, color=ft.Colors.ON_SURFACE_VARIANT)] if subtitle else []),
        spacing=2, tight=True,
    )
    left = [leading, title_col] if leading else [title_col]
    return ft.Row(
        [ft.Row(left, spacing=8, expand=True), *(actions or [])],
        spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def section(title: str, controls: list[ft.Control], icon=None, actions: list[ft.Control] | None = None,
            **card_kwargs) -> ft.Container:
    """Карточка-секция с заголовком."""
    head = [ft.Icon(icon, size=18, color=ft.Colors.PRIMARY)] if icon else []
    head.append(ft.Text(title, size=15, weight=ft.FontWeight.W_600, expand=True))
    head.extend(actions or [])
    return card(ft.Column([ft.Row(head, spacing=8), *controls], spacing=12), **card_kwargs)


def pill(text: str, color: str, icon=None) -> ft.Container:
    """Цветная «таблетка»: статус, оплата, срок."""
    parts = [ft.Icon(icon, size=14, color=color)] if icon else []
    parts.append(ft.Text(text, size=12, weight=ft.FontWeight.W_600, color=color))
    return ft.Container(
        ft.Row(parts, spacing=4, tight=True),
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.12, color),
    )


def status_style(code: str) -> tuple[str, str]:
    return STATUS_STYLES.get(code, (code, ft.Colors.GREY))


def status_chip(code: str) -> ft.Container:
    label, color = status_style(code)
    return pill(label, color, ft.Icons.CIRCLE)


def tight(control: ft.Control, col=None, end: bool = False) -> ft.Row:
    """Кладёт контрол в строку, чтобы он занимал свою ширину, а не всю колонку сетки."""
    return ft.Row([control], col=col, tight=not end,
                  alignment=ft.MainAxisAlignment.END if end else ft.MainAxisAlignment.START)


def paid_chip(paid: bool) -> ft.Container:
    return pill("Оплачен", ft.Colors.GREEN, ft.Icons.CHECK_CIRCLE) if paid else         pill("Не оплачен", ft.Colors.RED_400, ft.Icons.SCHEDULE)


def kv_row(label: str, value: str, bold: bool = False, color=None) -> ft.Row:
    """Строка «подпись …… значение» для расчётов и сводок."""
    weight = ft.FontWeight.W_700 if bold else None
    return ft.Row([
        ft.Text(label, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
        ft.Text(value, weight=weight, color=color, size=16 if bold else 14),
    ])


def empty_state(text: str, icon=ft.Icons.INBOX) -> ft.Container:
    return ft.Container(
        ft.Column([ft.Icon(icon, size=40, color=ft.Colors.OUTLINE),
                   ft.Text(text, color=ft.Colors.ON_SURFACE_VARIANT)],
                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True),
        alignment=ft.alignment.center, padding=40,
    )
