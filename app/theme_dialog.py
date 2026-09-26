"""Окно «Тема оформления»: карточки-превью тем как на vscodethemes.com — фон, кусочек кода
в цветах темы и акцент. Тема применяется сразу по клику, окно остаётся открытым."""
from typing import Callable

import flet as ft

from app import theme

SWATCH_COL = {"xs": 6, "sm": 4}


def _code_preview(p: theme.Palette) -> ft.Container:
    """Мини-«редактор»: две строки кода в цветах темы и полоска акцента."""
    kw, string, fn = p.syntax
    style = dict(size=11, font_family=theme.FONT_FAMILY)
    lines = [
        ft.Text(spans=[ft.TextSpan("def ", ft.TextStyle(color=kw)), ft.TextSpan("price", ft.TextStyle(color=fn)),
                       ft.TextSpan("(", ft.TextStyle(color=p.fg)), ft.TextSpan('"PLA"', ft.TextStyle(color=string)),
                       ft.TextSpan("):", ft.TextStyle(color=p.fg))], max_lines=1, no_wrap=True, **style),
        ft.Text(spans=[ft.TextSpan("  return ", ft.TextStyle(color=kw)),
                       ft.TextSpan("total", ft.TextStyle(color=p.fg))], max_lines=1, no_wrap=True, **style),
        ft.Row([ft.Container(width=34, height=6, border_radius=3, bgcolor=p.accent),
                ft.Container(width=22, height=6, border_radius=3, bgcolor=p.line)], spacing=4),
    ]
    return ft.Container(ft.Column(lines, spacing=4, tight=True), bgcolor=p.card, border_radius=8, padding=8,
                        border=ft.border.all(1, p.border), clip_behavior=ft.ClipBehavior.HARD_EDGE)


def _system_preview() -> ft.Container:
    """«Как в системе» — половина светлой темы, половина тёмной."""
    light, dark = theme.PALETTES["light"], theme.PALETTES["dark"]
    return ft.Row([ft.Container(_code_preview(light), expand=True),
                   ft.Container(_code_preview(dark), expand=True)], spacing=4)


class ThemeDialog:
    def __init__(self, page: ft.Page, on_pick: Callable[[str], None]):
        self.page = page
        self.on_pick = on_pick
        self.current = theme.SYSTEM_THEME
        self.body = ft.Column(spacing=10, tight=True, scroll=ft.ScrollMode.AUTO)
        self.dialog = ft.AlertDialog(
            title=ft.Text("Тема оформления"),
            content=ft.Container(self.body, width=620, height=520),
            actions=[ft.FilledButton("Готово", on_click=lambda e: page.close(self.dialog))],
        )

    def open(self, current: str) -> None:
        self.current = theme.normalize_theme(current)
        self._render()
        self.page.open(self.dialog)

    def _pick(self, key: str) -> None:
        self.current = key
        self.on_pick(key)
        self._render()
        self.dialog.update()

    def _swatch(self, key: str) -> ft.Container:
        selected = key == self.current
        if key == theme.SYSTEM_THEME:
            p, preview = theme.PALETTES["dark"], _system_preview()
            bg = ft.Colors.SECONDARY_CONTAINER
            name_color = ft.Colors.ON_SURFACE
        else:
            p = theme.PALETTES[key]
            preview, bg, name_color = _code_preview(p), p.bg, p.fg
        mark = (ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=p.accent if key != theme.SYSTEM_THEME
                        else ft.Colors.PRIMARY) if selected else theme.dot(p.accent, 10))
        return ft.Container(
            ft.Column([preview,
                       ft.Row([mark, ft.Text(theme.theme_name(key), size=12, color=name_color, max_lines=1,
                                             overflow=ft.TextOverflow.ELLIPSIS, expand=True)],
                              spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)],
                      spacing=8, tight=True),
            bgcolor=bg, border_radius=14, padding=10, col=SWATCH_COL,
            border=ft.border.all(2, ft.Colors.PRIMARY) if selected else ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            on_click=lambda e, k=key: self._pick(k), tooltip=theme.theme_name(key),
        )

    def _render(self) -> None:
        light = [k for k, p in theme.PALETTES.items() if not p.dark]
        dark = [k for k, p in theme.PALETTES.items() if p.dark]
        self.body.controls = [
            ft.Text("Цвета всего приложения — как темы редактора в VS Code. Применяется сразу.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            theme.grid([self._swatch(theme.SYSTEM_THEME)]),
            theme.eyebrow("Светлые"),
            theme.grid([self._swatch(k) for k in light]),
            theme.eyebrow("Тёмные"),
            theme.grid([self._swatch(k) for k in dark]),
        ]
