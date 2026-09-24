"""Единый визуальный язык приложения: тема Material 3 и карточная вёрстка."""
import flet as ft

ACCENT_COLOR = "#3D5AFE"

CARD_RADIUS = 16
BUTTON_RADIUS = 12
SPACING = 16
PAGE_PADDING = 24

LIGHT_THEME = ft.Theme(color_scheme_seed=ACCENT_COLOR, use_material3=True)
DARK_THEME = ft.Theme(color_scheme_seed=ACCENT_COLOR, use_material3=True)

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
