"""Боковое меню вместо ft.NavigationRail.

У NavigationRail в развёрнутом виде пункты центрируются по ширине подписи, поэтому иконки
у длинных названий («Информация о пластике») уезжали влево. Здесь у каждой иконки своя
фиксированная колонка, подпись — справа от неё; в свёрнутом виде — только иконки с подсказками."""
from typing import Callable

import flet as ft

from app import theme

EXTENDED_WIDTH = 276
COLLAPSED_WIDTH = 72
ITEM_HEIGHT = 40


class Destination:
    def __init__(self, icon, selected_icon, label: str):
        self.icon, self.selected_icon, self.label = icon, selected_icon, label


class Action:
    """Кнопка внизу меню (тема, экспорт) — выглядит как пункт меню, но не выбирается."""

    def __init__(self, icon, label: str, on_click: Callable[[ft.ControlEvent], None]):
        self.icon, self.label, self.on_click = icon, label, on_click


class Sidebar(ft.Container):
    def __init__(self, destinations: list[Destination], on_change: Callable[[ft.ControlEvent | None], None]):
        super().__init__(bgcolor=ft.Colors.SURFACE, padding=ft.padding.symmetric(horizontal=12, vertical=12))
        self.destinations = destinations
        self.on_change = on_change
        self._selected = 0
        self.extended = True
        self.leading: ft.Control | None = None
        self.actions: list[Action] = []
        self._render()

    @property
    def selected_index(self) -> int:
        return self._selected

    @selected_index.setter
    def selected_index(self, value: int) -> None:
        self._selected = value
        self._render()

    def set_layout(self, extended: bool, leading: ft.Control | None, actions: list[Action]) -> None:
        self.extended, self.leading, self.actions = extended, leading, actions
        self._render()

    def _select(self, index: int, e: ft.ControlEvent) -> None:
        self._selected = index
        self._render()
        self.on_change(e)

    def _render(self) -> None:
        self.width = EXTENDED_WIDTH if self.extended else COLLAPSED_WIDTH
        self.padding = ft.padding.symmetric(horizontal=12 if self.extended else 10, vertical=12)
        items = [
            self._item(d.selected_icon if i == self._selected else d.icon, d.label, i == self._selected,
                       lambda e, i=i: self._select(i, e))
            for i, d in enumerate(self.destinations)
        ]
        bottom = [self._item(a.icon, a.label, False, a.on_click) for a in self.actions]
        self.content = ft.Column(
            [*([self.leading] if self.leading else []), *items,
             ft.Divider(height=16, color=ft.Colors.OUTLINE_VARIANT), *bottom],
            spacing=4, scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _item(self, icon, label: str, selected: bool, on_click) -> ft.Container:
        color = ft.Colors.ON_SURFACE if selected else ft.Colors.ON_SURFACE_VARIANT
        icon_box = ft.Container(ft.Icon(icon, size=20, color=color), width=24, alignment=ft.alignment.center)
        if self.extended:
            body = ft.Row([icon_box, ft.Text(label, size=13, color=ft.Colors.ON_SURFACE, max_lines=1,
                                             overflow=ft.TextOverflow.ELLIPSIS, expand=True,
                                             font_family=theme.FONT_FAMILY_MEDIUM if selected else None)],
                          spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        else:
            body = icon_box
        base = ft.Colors.SECONDARY_CONTAINER if selected else ft.Colors.TRANSPARENT
        item = ft.Container(
            body, height=ITEM_HEIGHT, border_radius=10, bgcolor=base, on_click=on_click,
            padding=ft.padding.symmetric(horizontal=12 if self.extended else 0),
            alignment=ft.alignment.center_left if self.extended else ft.alignment.center,
            tooltip=None if self.extended else label,
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

        def hover(e: ft.ControlEvent) -> None:
            item.bgcolor = base if selected or e.data != "true" else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
            if item.page:
                item.update()

        item.on_hover = hover
        return item
