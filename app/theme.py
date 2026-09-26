"""Единый визуальный язык приложения: спокойная нейтральная палитра (zinc) в стиле дашбордов
shadcn/ui, моноширинный JetBrains Mono, карточки-виджеты с тонкой рамкой, крупные цифры,
мелкие заголовки капсом; синий — только для объёмов в данных, цвета статусов — для статусов."""
from typing import Iterable, NamedTuple

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


class Palette(NamedTuple):
    """Цветовая тема приложения — как тема редактора в VS Code (vscodethemes.com).
    syntax — цвета «ключевое слово / строка / функция» для превью в окне выбора темы."""
    name: str
    dark: bool
    bg: str        # фон окна
    card: str      # фон карточек и меню
    fg: str        # основной текст
    muted: str     # приглушённый текст
    border: str    # тонкие рамки карточек
    subtle: str    # выбранный пункт меню, подложки
    line: str      # рамки полей ввода
    accent: str    # кнопки, логотип
    syntax: tuple[str, str, str]


PALETTES: dict[str, Palette] = {
    "light": Palette("Светлая", False, "#FAFAFA", "#FFFFFF", "#09090B", "#71717A", "#E4E4E7", "#F4F4F5",
                     "#D4D4D8", "#09090B", ("#7C3AED", "#059669", "#2563EB")),
    "dark": Palette("Тёмная", True, "#0A0A0B", "#141417", "#FAFAFA", "#A1A1AA", "#27272A", "#1C1C20",
                    "#3F3F46", "#FAFAFA", ("#C084FC", "#34D399", "#60A5FA")),
    "github_light": Palette("GitHub Light", False, "#F6F8FA", "#FFFFFF", "#1F2328", "#656D76", "#D0D7DE",
                            "#EAEEF2", "#AFB8C1", "#0969DA", ("#CF222E", "#0A3069", "#8250DF")),
    "catppuccin_latte": Palette("Catppuccin Latte", False, "#E6E9EF", "#EFF1F5", "#4C4F69", "#6C6F85",
                                "#CCD0DA", "#DCE0E8", "#BCC0CC", "#8839EF", ("#8839EF", "#40A02B", "#1E66F5")),
    "solarized_light": Palette("Solarized Light", False, "#EEE8D5", "#FDF6E3", "#073642", "#657B83",
                               "#DDD6C1", "#EEE8D5", "#C9C2AE", "#268BD2", ("#859900", "#2AA198", "#268BD2")),
    "github_dark": Palette("GitHub Dark", True, "#010409", "#0D1117", "#E6EDF3", "#8D96A0", "#30363D",
                           "#161B22", "#484F58", "#2F81F7", ("#FF7B72", "#A5D6FF", "#D2A8FF")),
    "one_dark": Palette("One Dark Pro", True, "#21252B", "#282C34", "#ABB2BF", "#7F848E", "#3E4452",
                        "#2C313A", "#4B5263", "#61AFEF", ("#C678DD", "#98C379", "#61AFEF")),
    "dracula": Palette("Dracula", True, "#21222C", "#282A36", "#F8F8F2", "#A0A8CD", "#343746", "#44475A",
                       "#6272A4", "#BD93F9", ("#FF79C6", "#F1FA8C", "#50FA7B")),
    "monokai": Palette("Monokai", True, "#1E1F1C", "#272822", "#F8F8F2", "#A09F93", "#3E3D32", "#3E3D32",
                       "#575852", "#A6E22E", ("#F92672", "#E6DB74", "#A6E22E")),
    "tokyo_night": Palette("Tokyo Night", True, "#16161E", "#1A1B26", "#C0CAF5", "#787C99", "#292E42",
                           "#24283B", "#3B4261", "#7AA2F7", ("#BB9AF7", "#9ECE6A", "#7AA2F7")),
    "catppuccin_mocha": Palette("Catppuccin Mocha", True, "#11111B", "#1E1E2E", "#CDD6F4", "#A6ADC8",
                                "#313244", "#313244", "#45475A", "#CBA6F7", ("#CBA6F7", "#A6E3A1", "#89B4FA")),
    "nord": Palette("Nord", True, "#2E3440", "#3B4252", "#ECEFF4", "#A5AFC2", "#434C5E", "#434C5E",
                    "#4C566A", "#88C0D0", ("#81A1C1", "#A3BE8C", "#88C0D0")),
    "gruvbox_dark": Palette("Gruvbox Dark", True, "#1D2021", "#282828", "#EBDBB2", "#A89984", "#3C3836",
                            "#32302F", "#504945", "#FABD2F", ("#FB4934", "#B8BB26", "#8EC07C")),
    "night_owl": Palette("Night Owl", True, "#010E1A", "#011627", "#D6DEEB", "#8BA3B8", "#122D42", "#0B2942",
                         "#1D3B53", "#82AAFF", ("#C792EA", "#ECC48D", "#82AAFF")),
    "solarized_dark": Palette("Solarized Dark", True, "#00212B", "#002B36", "#EEE8D5", "#93A1A1", "#0F3B47",
                              "#073642", "#2A5561", "#268BD2", ("#859900", "#2AA198", "#268BD2")),
}

# «Как в системе» — светлая или тёмная по настройке Windows; остальное — ключи PALETTES.
SYSTEM_THEME = "system"
SYSTEM_THEME_NAME = "Как в системе"


def _scheme(p: Palette) -> ft.ColorScheme:
    """Токены в духе shadcn: background / card / foreground / muted / border + акцент темы."""
    on_accent = p.bg if p.dark else "#FFFFFF"
    return ft.ColorScheme(
        primary=p.accent, on_primary=on_accent,
        primary_container=p.subtle, on_primary_container=p.fg,
        secondary=p.muted, on_secondary=p.bg,
        secondary_container=p.subtle, on_secondary_container=p.fg,
        tertiary=DATA, on_tertiary="#FFFFFF",
        error=ERR, on_error="#FFFFFF",
        surface=p.card, on_surface=p.fg,
        on_surface_variant=p.muted,
        surface_variant=p.subtle, surface_container_high=p.subtle, surface_container=p.subtle,
        surface_container_low=p.bg, surface_container_lowest=p.card,
        outline=p.line, outline_variant=p.border,
        surface_tint=ft.Colors.TRANSPARENT,
        inverse_surface=p.fg, on_inverse_surface=p.bg,
    )


def _button_shape() -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=BUTTON_RADIUS)


def _rounded_button_themes() -> dict:
    """Общие скруглённые темы кнопок — применяются ко всем темам,
    чтобы BUTTON_RADIUS действовал на все кнопки без изменений в экранах."""
    return dict(
        elevated_button_theme=ft.ElevatedButtonTheme(shape=_button_shape()),
        outlined_button_theme=ft.OutlinedButtonTheme(shape=_button_shape()),
        text_button_theme=ft.TextButtonTheme(shape=_button_shape()),
        filled_button_theme=ft.FilledButtonTheme(shape=_button_shape()),
        icon_button_theme=ft.IconButtonTheme(shape=_button_shape()),
    )


def build_theme(p: Palette) -> ft.Theme:
    return ft.Theme(
        color_scheme=_scheme(p), use_material3=True, font_family=FONT_FAMILY,
        scaffold_bgcolor=p.bg,
        tooltip_theme=ft.TooltipTheme(text_style=ft.TextStyle(size=12, font_family=FONT_FAMILY)),
        **_rounded_button_themes(),
    )


LIGHT_THEME = build_theme(PALETTES["light"])
DARK_THEME = build_theme(PALETTES["dark"])


def normalize_theme(value: str | None) -> str:
    """Сохранённое значение темы → «system» или ключ PALETTES (неизвестное считается «system»)."""
    return value if value in PALETTES else SYSTEM_THEME


def theme_name(value: str | None) -> str:
    key = normalize_theme(value)
    return SYSTEM_THEME_NAME if key == SYSTEM_THEME else PALETTES[key].name


def theme_icon(value: str | None):
    key = normalize_theme(value)
    if key == SYSTEM_THEME:
        return ft.Icons.BRIGHTNESS_AUTO
    if key in ("light", "dark"):
        return ft.Icons.LIGHT_MODE if key == "light" else ft.Icons.DARK_MODE
    return ft.Icons.PALETTE_OUTLINED


def apply_theme(page: ft.Page, value: str | None) -> None:
    """Ставит тему странице: «system» — светлая/тёмная по системе, иначе — выбранная палитра."""
    key = normalize_theme(value)
    if key == SYSTEM_THEME:
        page.theme, page.dark_theme, page.theme_mode = LIGHT_THEME, DARK_THEME, ft.ThemeMode.SYSTEM
        return
    p = PALETTES[key]
    page.theme = page.dark_theme = build_theme(p)
    page.theme_mode = ft.ThemeMode.DARK if p.dark else ft.ThemeMode.LIGHT


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


def dropdown(label: str, width: int = 240, stretch: bool = False, **kwargs) -> ft.Dropdown | ft.DropdownM2:
    """Выпадающий список в едином стиле. В Flet 0.27 Dropdown (M3 DropdownMenu) не растягивается
    по колонке, а без ширины сжимается по содержимому («Мате / риал») — поэтому ширина фиксированная.
    stretch=True — во всю ширину колонки сетки, как соседние поля: DropdownM2 (DropdownButtonFormField)
    с тем же API (options / value / on_change); col передаётся в kwargs."""
    defaults = dict(label=label, border_radius=FIELD_RADIUS, text_size=14,
                    border_color=ft.Colors.OUTLINE, focused_border_color=ft.Colors.ON_SURFACE,
                    label_style=ft.TextStyle(size=13, color=ft.Colors.ON_SURFACE_VARIANT))
    if stretch:
        defaults.update(focused_border_width=1.5, bgcolor=ft.Colors.SURFACE)
        defaults.update(kwargs)
        return ft.DropdownM2(**defaults)
    defaults["width"] = width
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
