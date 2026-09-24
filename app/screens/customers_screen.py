"""Экран «Клиенты»: список с поиском и карточка клиента с историей заказов."""
import flet as ft

import db
import pricing
from app import theme


class CustomersScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.search_text = ""
        self.selected_customer_id: int | None = None
        self._notes_field: ft.TextField | None = None

        self.search_field = ft.TextField(label="Поиск клиента", on_change=self._on_search)
        self.list_view = ft.ListView(expand=True, spacing=theme.SPACING)
        self.detail_column = ft.Column(spacing=8)
        self.detail_card = theme.card(self.detail_column, visible=False)

        self.controls = [theme.card(self.search_field), self.list_view, self.detail_card]
        self.refresh()

    def _on_search(self, e: ft.ControlEvent) -> None:
        self.search_text = self.search_field.value or ""
        self.refresh()

    def refresh(self, from_sync: bool = False) -> None:
        customers = db.list_customers(self.search_text.strip())
        self.list_view.controls = [self._customer_tile(c) for c in customers] or [
            ft.Text("Клиентов нет.", italic=True)
        ]
        if self.selected_customer_id is not None:
            self._render_detail(self.selected_customer_id, from_sync=from_sync)
        if self.page:
            self.update()

    def _customer_tile(self, c) -> ft.Control:
        subtitle = f"{c['orders_count']} заказ(ов) · оплачено {pricing.money(c['paid_total'])}"
        if c["debt_total"]:
            subtitle += f" · долг {pricing.money(c['debt_total'])}"
        return theme.card(
            ft.ListTile(
                title=ft.Text(c["name"]),
                subtitle=ft.Text(subtitle),
                on_click=lambda e, cid=c["id"]: self._open_customer(cid),
            ),
            padding=0,
        )

    def _open_customer(self, customer_id: int) -> None:
        self.selected_customer_id = customer_id
        self._render_detail(customer_id)
        self.update()

    def _render_detail(self, customer_id: int, from_sync: bool = False) -> None:
        customer = db.get_customer(customer_id)
        if not customer:
            self.detail_card.visible = False
            self.selected_customer_id = None
            return
        if from_sync and self.detail_column.controls:
            # notes_field — TextField с сохранением по on_blur: во время live-sync
            # переиспользуем текущий контрол, чтобы не затереть незасохранённый ввод.
            notes_field = self._notes_field
        else:
            notes_field = ft.TextField(
                label="Заметки", value=customer["notes"] or "", multiline=True,
                on_blur=lambda e, cid=customer_id: db.update_customer(cid, notes=notes_field.value),
            )
            self._notes_field = notes_field
        orders = [o for o in db.list_orders("all", limit=200) if o["customer_id"] == customer_id]
        order_rows = [
            ft.Text(f"#{o['id']} · {db.STATUSES.get(o['status'], o['status'])} · {pricing.money(o['price'])}")
            for o in orders
        ] or [ft.Text("Заказов пока нет.", italic=True)]

        self.detail_card.visible = True
        self.detail_column.controls = [
            ft.Text(customer["name"], size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"Контакт: {customer['contact'] or '—'}"),
            notes_field,
            ft.Text("История заказов:", weight=ft.FontWeight.BOLD),
            *order_rows,
        ]
