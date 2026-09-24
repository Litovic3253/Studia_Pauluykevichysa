"""Экран «Заказы»: список с фильтрами и поиском, переход в карточку заказа."""
from typing import Callable

import flet as ft

import db
import pricing
from app import theme

FILTERS = [("active", "Активные"), ("unpaid", "Неоплаченные"), ("done", "Завершённые"), ("all", "Все")]


class OrdersScreen(ft.Column):
    def __init__(self, on_open_order: Callable[[int], None]):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.on_open_order = on_open_order
        self.kind = "active"
        self.search_text = ""

        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[ft.Tab(text=label) for _, label in FILTERS],
            on_change=self._on_filter_change,
        )
        self.search_field = ft.TextField(
            label="Поиск по клиенту / контакту / описанию",
            on_change=self._on_search_change,
        )
        self.list_view = ft.ListView(expand=True, spacing=theme.SPACING)

        self.controls = [
            theme.card(ft.Column([self.tabs, self.search_field], spacing=theme.SPACING)),
            self.list_view,
        ]
        self._render()

    def _on_filter_change(self, e: ft.ControlEvent) -> None:
        self.kind = FILTERS[self.tabs.selected_index][0]
        self.refresh()

    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self.search_text = self.search_field.value or ""
        self.refresh()

    def refresh(self) -> None:
        self._render()
        if self.page:
            self.update()

    def _render(self) -> None:
        text = self.search_text.strip()
        orders = db.search_orders(text) if text else db.list_orders(self.kind)
        self.list_view.controls = [self._order_tile(o) for o in orders] or [
            ft.Text("Заказов нет.", italic=True)
        ]

    def _order_tile(self, o) -> ft.Control:
        mark = pricing.deadline_mark(o)
        subtitle = f"{db.STATUSES.get(o['status'], o['status'])} · {pricing.money(o['price'])}"
        if not o["paid"]:
            subtitle += " · не оплачен"
        if mark:
            subtitle += f" · {mark}"
        return theme.card(
            ft.ListTile(
                title=ft.Text(f"#{o['id']} {o['client']}"),
                subtitle=ft.Text(subtitle),
                on_click=lambda e, oid=o["id"]: self.on_open_order(oid),
            ),
            padding=0,
        )
