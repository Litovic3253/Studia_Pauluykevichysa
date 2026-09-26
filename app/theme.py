"""Единый визуальный язык приложения: спокойная нейтральная палитра (zinc) в стиле дашбордов
shadcn/ui, моноширинный JetBrains Mono, карточки-виджеты с тонкой рамкой, крупные цифры,
мелкие заголовки капсом; синий — только для объёмов в данных, цвета статусов — для статусов."""
from typing import Iterable

import flet as ft

FONT_FAMILY = "JetBrains Mono"
FONT_FAMILY_MEDIUM = "JetBrains Mono Medium"
# Файлы шрифтов лежат в assets/fonts (лицензия OFL — assets/fonts/OFL.txt).
FONTS = {
    FONT_FAMILY: "fonts/JetBrainsMono-Regular.ttf",
    FONT_FAMILY_MEDIUM: "fonts/JetBrainsMono-Medium.ttf",
}

# Палитра данных и статусов (одинаково читается на светлой и тёмной теме).
DATA = "#3B82F6"      # синий — объёмы, акцент в графиках
OK = "#10B981"        # emerald — всё хорошо, оплачено
WARN = "#F59E0B"      # amber — внимание
ERR = "#F43F5E"       # rose — ошибка, просрочка, долг
VIOLET = "#8B5CF6"
IDLE = "#A1A1AA"      # zinc-400 — нейтральное, неактивное

CARD_RADIUS = 20
BUTTON_RADIUS = 10
SPACING = 12
PAGE_PADDING = 24
FIELD_RADIUS = 10

# Ширина контента на больших мониторах — дальше строки становятся нечитаемо длинными.
MAX_CONTENT_WIDTH = 1180
# Ниже этой ширины окна: меню только иконками, «Клиенты» — список ИЛИ карточка.
COMPACT_WIDTH = 900
# От этой ширины окна меню показывает подписи рядом с иконками.
WIDE_WIDTH = 1280

# Статус → (подпись без эмодзи, цвет точки).
STATUS_STYLES = {
    "new": ("Новый", DATA),
    "queued": ("В очереди", IDLE),
    "printing": ("Печатается", VIOLET),
    "post": ("Постобработка", WARN),
    "ready": ("Готов", OK),
    "delivered": ("Выдан", "#71717A"),
    "cancelled": ("Отменён", ERR),
}

# Тени как у виджетов на Motion: «в покое» почти незаметная, при наведении и «поднят» — глубокая.
SHADOW_REST = ft.BoxShadow(blur_radius=2, spread_radius=0, offset=ft.Offset(0, 1),
                           color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK))
SHADOW_HOVER = ft.BoxShadow(blur_radius=28, spread_radius=-10, offset=ft.Offset(0, 14),
                            color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK))
SHADOW_LIFTED = ft.BoxShadow(blur_radius=60, spread_radius=-16, offset=ft.Offset(0, 28),
                             color=ft.Colors.with_opacity(0.45, ft.Colors.BLACK))

# Пружинистая кривая для подъёма карточек (аналог spring с bounce) и мягкая — для рамок.
SPRING = ft.AnimationCurve.EASE_OUT_BACK  # пружинистая кривая, как spring с bounce в Motion
HOVER_ANIMATION = ft.animation.Animation(220, ft.AnimationCurve.EASE_OUT)
LIFT_ANIMATION = ft.animation.Animation(280, SPRING)


def _scheme(dark: bool) -> ft.ColorScheme:
    """Нейтральные токены shadcn (zinc): background / card / foreground / muted / border."""
    if dark:
        card_bg, fg, muted, border, subtle, line = "#141417", "#FAFAFA", "#A1A1AA", "#27272A", "#1C1C20", "#3F3F46"
    else:
        card_bg, fg, muted, border, subtle, line = "#FFFFFF", "#09090B", "#71717A", "#E4E4E7", "#F4F4F5", "#D4D4D8"
    bg = background(dark)
    return ft.ColorScheme(
        primary=fg, on_primary=bg,
        primary_container=subtle, on_primary_container=fg,
        secondary=muted, on_secondary=bg,
        secondary_container=subtle, on_secondary_container=fg,
        tertiary=DATA, on_tertiary="#FFFFFF",
        error=ERR, on_error="#FFFFFF",
        surface=card_bg, on_surface=fg,
        on_surface_variant=muted,
        surface_variant=subtle, surface_container_high=subtle, surface_container=subtle,
        surface_container_low=bg, surface_container_lowest=card_bg,
        outline=line, outline_variant=border,
        surface_tint=ft.Colors.TRANSPARENT,
        inverse_surface=fg, on_inverse_surface=bg,
    )


def background(dark: bool) -> str:
    return "#0A0A0B" if dark else "#FAFAFA"


def _button_shape() -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=BUTTON_RADIUS)


def _rounded_button_themes() -> dict:
    """Общие скруглённые темы кнопок — применяются и к светлой, и к тёмной теме,
    чтобы BUTTON_RADIUS действовал на все кнопки без изменений в экранах."""
    return dict(
        elevated_button_theme=ft.ElevatedButtonTheme(shape=_button_shape()),
        outlined_button_theme=ft.OutlinedButtonTheme(shape=_button_shape()),
        text_button_theme=ft.TextButtonTheme(shape=_button_shape()),
        filled_button_theme=ft.FilledButtonTheme(shape=_button_shape()),
        icon_button_theme=ft.IconButtonTheme(shape=_button_shape()),
    )


def _theme(dark: bool) -> ft.Theme:
    return ft.Theme(
        color_scheme=_scheme(dark), use_material3=True, font_family=FONT_FAMILY,
        scaffold_bgcolor=background(dark),
        tooltip_theme=ft.TooltipTheme(text_style=ft.TextStyle(size=12, font_family=FONT_FAMILY)),
        **_rounded_button_themes(),
    )


LIGHT_THEME = _theme(dark=False)
DARK_THEME = _theme(dark=True)

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


def add_hover(container: ft.Container, lift: bool = False) -> ft.Container:
    """Реакция на наведение: рамка темнеет (как «ring-foreground/40»), тень углубляется;
    lift=True — карточка ещё и пружинисто приподнимается (для кликабельных карточек)."""
    base_border, base_shadow = container.border, container.shadow
    container.animate = HOVER_ANIMATION
    if lift:
        container.scale = 1
        container.animate_scale = LIFT_ANIMATION

    def on_hover(e: ft.ControlEvent) -> None:
        hovered = e.data == "true"
        if hovered:
            container.border = ft.border.all(1, ft.Colors.with_opacity(0.4 if lift else 0.22, ft.Colors.ON_SURFACE))
            container.shadow = SHADOW_HOVER if lift else SHADOW_REST
        else:
            container.border, container.shadow = base_border, base_shadow
        if lift:
            container.scale = 1.015 if hovered else 1
        if container.page:
            container.update()

    container.on_hover = on_hover
    return container


def card(content: ft.Control, hover: str = "auto", **container_kwargs) -> ft.Container:
    """Единая обёртка «карточка»: крупное скругление, фон card, тонкая рамка border и почти
    незаметная тень — используется всеми экранами вместо голого Column/Row.
    hover: "lift" — подъём при наведении, "soft" — только рамка, "none" — без реакции;
    "auto" — lift для кликабельных карточек, soft для остальных."""
    defaults = dict(
        content=content,
        padding=18,
        border_radius=CARD_RADIUS,
        bgcolor=ft.Colors.SURFACE,
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
        shadow=SHADOW_REST,
    )
    defaults.update(container_kwargs)
    container = ft.Container(**defaults)
    if hover == "auto":
        hover = "lift" if container_kwargs.get("on_click") else "soft"
    if hover != "none":
        add_hover(container, lift=hover == "lift")
    return container


def appear(controls: list[ft.Control], step_ms: int = 55, base_ms: int = 380) -> None:
    """Готовит контролы к «появлению лесенкой» (как стартовая анимация виджетов в Motion):
    прозрачные и чуть ниже; show_appeared() потом проявляет их — чем дальше, тем позже."""
    for i, c in enumerate(controls):
        c.opacity = 0
        c.offset = ft.Offset(0, 0.06)
        c.animate_opacity = ft.animation.Animation(base_ms + i * step_ms, ft.AnimationCurve.EASE_OUT)
        c.animate_offset = ft.animation.Animation(base_ms + i * step_ms, ft.AnimationCurve.EASE_OUT_CUBIC)


def show_appeared(controls: list[ft.Control]) -> None:
    for c in controls:
        c.opacity = 1
        c.offset = ft.Offset(0, 0)


def eyebrow(text: str, color=None) -> ft.Text:
    """Мелкий заголовок капсом с разрядкой — как подписи виджетов."""
    return ft.Text(text.upper(), size=11, color=color or ft.Colors.ON_SURFACE_VARIANT,
                   style=ft.TextStyle(letter_spacing=1.3), max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)


def big_number(value: str, unit: str | None = None, color=None) -> ft.Text:
    """Крупная цифра с приглушённой единицей измерения."""
    spans = [ft.TextSpan(value, ft.TextStyle(size=28, color=color or ft.Colors.ON_SURFACE,
                                             letter_spacing=-0.8))]
    if unit:
        spans.append(ft.TextSpan("\u00a0" + unit, ft.TextStyle(size=13, color=ft.Colors.ON_SURFACE_VARIANT)))
    return ft.Text(spans=spans, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)


def dot(color: str, size: int = 8) -> ft.Container:
    return ft.Container(width=size, height=size, border_radius=size, bgcolor=color)


def delta_text(value: float, good: str = "up", suffix: str = "") -> ft.Text:
    """«↑ 12% к прошлому месяцу»: зелёный, если изменение в хорошую сторону."""
    up = value >= 0
    color = OK if up == (good == "up") else ERR
    spans = [ft.TextSpan(f"{'↑' if up else '↓'} {abs(value):.0f}%", ft.TextStyle(color=color))]
    if suffix:
        spans.append(ft.TextSpan(f" {suffix}", ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT)))
    return ft.Text(spans=spans, size=12)


def thin_bar(share: float, color=None, height: int = 3) -> ft.ProgressBar:
    """Тонкая полоска-доля: дорожка foreground/8 и заполнение."""
    return ft.ProgressBar(value=max(0.0, min(share, 1.0)),
                          color=color or ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE),
                          bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                          bar_height=height, border_radius=height)


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
    defaults = dict(label=label, border_radius=FIELD_RADIUS, width=width, text_size=14,
                    border_color=ft.Colors.OUTLINE, focused_border_color=ft.Colors.ON_SURFACE)
    defaults.update(kwargs)
    return ft.Dropdown(**defaults)


def in_col(control: ft.Control, col) -> ft.Row:
    """Обёртка для контролов, которые сами не растягиваются по колонке ResponsiveRow (Dropdown)."""
    return ft.Row([control], col=col)


def field(label: str, col=None, **kwargs) -> ft.TextField:
    """Текстовое поле в едином стиле."""
    defaults = dict(label=label, border_radius=FIELD_RADIUS, col=col or {"xs": 12, "md": 6}, text_size=14,
                    border_color=ft.Colors.OUTLINE, focused_border_color=ft.Colors.ON_SURFACE, focused_border_width=1.5,
                    label_style=ft.TextStyle(size=13, color=ft.Colors.ON_SURFACE_VARIANT))
    defaults.update(kwargs)
    return ft.TextField(**defaults)


# ---------- общие элементы экранов ----------

def page_header(title: str, subtitle: str | None = None, actions: list[ft.Control] | None = None,
                leading: ft.Control | None = None) -> ft.Control:
    """Шапка экрана: заголовок + подзаголовок слева, действия справа."""
    title_col = ft.Column(
        [ft.Text(title, size=24, font_family=FONT_FAMILY_MEDIUM, style=ft.TextStyle(letter_spacing=-0.6))]
        + ([ft.Text(subtitle, size=13, color=ft.Colors.ON_SURFACE_VARIANT)] if subtitle else []),
        spacing=4, tight=True,
    )
    left = [leading, title_col] if leading else [title_col]
    return ft.Row(
        [ft.Row(left, spacing=8, expand=True), *(actions or [])],
        spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def section(title: str, controls: list[ft.Control], icon=None, actions: list[ft.Control] | None = None,
            **card_kwargs) -> ft.Container:
    """Карточка-секция с мелким заголовком капсом, как у виджетов."""
    head = [ft.Icon(icon, size=14, color=ft.Colors.ON_SURFACE_VARIANT)] if icon else []
    head.append(ft.Container(eyebrow(title), expand=True))
    head.extend(actions or [])
    return card(ft.Column([ft.Row(head, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER), *controls],
                          spacing=14), **card_kwargs)


def pill(text: str, color: str, icon=None) -> ft.Container:
    """Тихая «таблетка»: точка (или иконка) цвета статуса, подпись, тонкая цветная рамка."""
    lead = dot(color) if icon in (None, ft.Icons.CIRCLE) else ft.Icon(icon, size=13, color=color)
    return ft.Container(
        ft.Row([lead, ft.Text(text, size=12, color=ft.Colors.ON_SURFACE)], spacing=6, tight=True,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.08, color),
        border=ft.border.all(1, ft.Colors.with_opacity(0.25, color)),
    )


def status_style(code: str) -> tuple[str, str]:
    return STATUS_STYLES.get(code, (code, IDLE))


def status_chip(code: str) -> ft.Container:
    label, color = status_style(code)
    return pill(label, color, ft.Icons.CIRCLE)


def tight(control: ft.Control, col=None, end: bool = False) -> ft.Row:
    """Кладёт контрол в строку, чтобы он занимал свою ширину, а не всю колонку сетки."""
    return ft.Row([control], col=col, tight=not end,
                  alignment=ft.MainAxisAlignment.END if end else ft.MainAxisAlignment.START)


def paid_chip(paid: bool, prepayment_text: str | None = None) -> ft.Container:
    """Оплата заказа; prepayment_text — «500 ₽», если клиент внёс предоплату, но ещё не всё."""
    if paid:
        return pill("Оплачен", OK)
    if prepayment_text:
        return pill(f"Предоплата {prepayment_text}", WARN)
    return pill("Не оплачен", ERR)


def kv_row(label: str, value: str, bold: bool = False, color=None) -> ft.Row:
    """Строка «подпись …… значение» для расчётов и сводок."""
    return ft.Row([
        ft.Text(label, color=ft.Colors.ON_SURFACE_VARIANT, expand=True, size=13),
        ft.Text(value, color=color, size=17 if bold else 13,
                font_family=FONT_FAMILY_MEDIUM if bold else None),
    ])


def empty_state(text: str, icon=ft.Icons.INBOX) -> ft.Container:
    return ft.Container(
        ft.Column([ft.Icon(icon, size=32, color=ft.Colors.OUTLINE),
                   ft.Text(text, color=ft.Colors.ON_SURFACE_VARIANT)],
                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True),
        alignment=ft.alignment.center, padding=40,
    )
