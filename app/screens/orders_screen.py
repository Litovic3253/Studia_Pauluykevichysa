"""Экран «Заказы»: фильтры со счётчиками, поиск, компактный адаптивный список."""
from datetime import date
from typing import Callable

import flet as ft

import db
import pricing
from app import theme

FILTERS = [("active", "Активные"), ("unpaid", "Неоплаченные"), ("done", "Завершённые"), ("all", "Все")]


def deadline_view(order) -> ft.Control:
    """Срок: дата + «через N дн.»; просрочка и «сегодня» подсвечиваются."""
    if not order["deadline"]:
        return ft.Text("без срока", size=13, color=ft.Colors.OUTLINE)
    date_text = pricing.fmt_date(order["deadline"])
    if order["status"] not in db.ACTIVE_STATUSES:
        return ft.Text(date_text, size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    days = (date.fromisoformat(order["deadline"]) - date.today()).days
    if days < 0:
        return theme.pill(f"{date_text} · просрочен", ft.Colors.RED, ft.Icons.WARNING_AMBER)
    if days <= 1:
        return theme.pill(f"{date_text} · {'сегодня' if days == 0 else 'завтра'}", ft.Colors.ORANGE_800,
                          ft.Icons.ALARM)
    return ft.Column([
        ft.Text(date_text, size=13),
        ft.Text(f"через {days} дн.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
    ], spacing=0, tight=True)


class OrdersScreen(ft.Column):
    def __init__(self, on_open_order: Callable[[int], None], on_new_order: Callable[[], None] | None = None):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.on_open_order = on_open_order
        self.on_new_order = on_new_order
        self.kind = "active"
        self.search_text = ""

        self.filter_buttons = ft.SegmentedButton(
            segments=[ft.Segment(value=k, label=ft.Text(label)) for k, label in FILTERS],
            selected={self.kind}, show_selected_icon=False, on_change=self._on_filter_change,
        )
        self.search_field = ft.TextField(
            hint_text="Поиск: клиент, контакт, описание", prefix_icon=ft.Icons.SEARCH,
            border_radius=theme.FIELD_RADIUS, dense=True, on_change=self._on_search_change,
            col={"xs": 12, "lg": 5},
        )
        self.header = ft.Container()
        self.list_view = ft.ListView(expand=True, spacing=8, padding=ft.padding.only(bottom=theme.SPACING))

        self.controls = [
            self.header,
            theme.grid([
                ft.Container(self.filter_buttons, col={"xs": 12, "lg": 7}),
                self.search_field,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.list_view,
        ]
        self._render()

    def _on_filter_change(self, e: ft.ControlEvent) -> None:
        self.kind = next(iter(self.filter_buttons.selected), "active")
        self.refresh()

    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self.search_text = self.search_field.value or ""
        self.refresh()

    def refresh(self) -> None:
        self._render()
        if self.page:
            self.update()

    def _render(self) -> None:
        counts = db.count_orders()
        for seg, (k, label) in zip(self.filter_buttons.segments, FILTERS):
            seg.label = ft.Text(f"{label} · {counts[k]}")

        actions = []
        if self.on_new_order:
            actions.append(ft.FilledButton("Новый заказ", icon=ft.Icons.ADD, on_click=lambda e: self.on_new_order()))
        self.header.content = theme.page_header(
            "Заказы", f"В работе {counts['active']} · ждут оплату {counts['unpaid']} · всего {counts['all']}", actions,
        )

        text = self.search_text.strip()
        orders = db.search_orders(text) if text else db.list_orders(self.kind, limit=200)
        if orders:
            self.list_view.controls = [self._order_row(o) for o in orders]
        else:
            message = "Ничего не найдено." if text else "Заказов нет."
            self.list_view.controls = [theme.empty_state(message, ft.Icons.RECEIPT_LONG)]

    def _order_row(self, o) -> ft.Control:
        title = ft.Text(f"#{o['id']}  {o['client']}", size=15, weight=ft.FontWeight.W_600,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        subtitle_parts = [p for p in [o["description"], o["material"]] if p]
        subtitle = ft.Text(" · ".join(subtitle_parts) or "без описания", size=12,
                           color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        price = ft.Column([
            ft.Text(pricing.money(o["price"]), size=15, weight=ft.FontWeight.W_700),
            theme.paid_chip(bool(o["paid"])),
        ], spacing=4, tight=True, horizontal_alignment=ft.CrossAxisAlignment.END)

        row = theme.grid([
            ft.Column([title, subtitle], spacing=2, tight=True, col={"xs": 12, "md": 4}),
            theme.tight(theme.status_chip(o["status"]), col={"xs": 6, "md": 3}),
            theme.tight(deadline_view(o), col={"xs": 6, "md": 2}),
            theme.tight(price, col={"xs": 12, "md": 3}, end=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, run_spacing=8)

        return theme.card(
            row, padding=ft.padding.symmetric(horizontal=18, vertical=12),
            on_click=lambda e, oid=o["id"]: self.on_open_order(oid), ink=True,
        )
