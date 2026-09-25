"""Экран «Клиенты»: на широком окне список и карточка рядом, на узком — список ИЛИ карточка."""
from typing import Callable

import flet as ft

import db
import pricing
from app import theme


class CustomersScreen(ft.Column):
    def __init__(self, on_open_order: Callable[[int], None] | None = None):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.on_open_order = on_open_order
        self.search_text = ""
        self.selected_customer_id: int | None = None
        self.compact = False
        self._notes_field: ft.TextField | None = None
        self._name_field: ft.TextField | None = None
        self._contact_field: ft.TextField | None = None

        self.header = ft.Container()
        self.search_field = ft.TextField(
            hint_text="Поиск клиента", prefix_icon=ft.Icons.SEARCH, border_radius=theme.FIELD_RADIUS,
            dense=True, on_change=self._on_search,
        )
        self.list_view = ft.ListView(expand=True, spacing=8, padding=ft.padding.only(bottom=theme.SPACING))
        self.list_panel = ft.Column([self.search_field, self.list_view], expand=5, spacing=12)
        self.detail_column = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self.detail_card = theme.card(self.detail_column, visible=False, expand=7)
        self.placeholder = theme.card(
            theme.empty_state("Выберите клиента в списке", ft.Icons.PERSON_SEARCH), expand=7,
        )

        self.controls = [
            self.header,
            ft.Row([self.list_panel, self.detail_card, self.placeholder], expand=True, spacing=theme.SPACING,
                   vertical_alignment=ft.CrossAxisAlignment.START),
        ]
        self.refresh()

    def set_compact(self, compact: bool) -> None:
        """Узкое окно: показываем либо список, либо карточку (с кнопкой «Назад»)."""
        if compact == self.compact:
            return
        self.compact = compact
        self.refresh(from_sync=True)

    def _on_search(self, e: ft.ControlEvent) -> None:
        self.search_text = self.search_field.value or ""
        self.refresh(from_sync=True)

    def refresh(self, from_sync: bool = False) -> None:
        customers = db.list_customers(self.search_text.strip())
        all_count = len(db.list_customers()) if self.search_text.strip() else len(customers)
        debtors = sum(1 for c in customers if c["debt_total"])
        self.header.content = theme.page_header(
            "Клиенты", f"{all_count} клиентов" + (f" · с долгом {debtors}" if debtors else ""),
        )
        self.list_view.controls = [self._customer_tile(c) for c in customers] or [
            theme.empty_state("Клиентов нет." if not self.search_text else "Никого не нашлось.", ft.Icons.PEOPLE_OUTLINE)
        ]
        if self.selected_customer_id is not None:
            self._render_detail(self.selected_customer_id, from_sync=from_sync)
        self._apply_visibility()
        if self.page:
            self.update()

    def _apply_visibility(self) -> None:
        selected = self.selected_customer_id is not None and self.detail_card.visible
        if self.compact:
            self.list_panel.visible = not selected
            self.placeholder.visible = False
        else:
            self.list_panel.visible = True
            self.placeholder.visible = not selected

    def _customer_tile(self, c) -> ft.Control:
        right = [ft.Text(f"{c['orders_count']} зак.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)]
        if c["debt_total"]:
            right.append(theme.pill(f"долг {pricing.money(c['debt_total'])}", ft.Colors.RED_400))
        else:
            right.append(ft.Text(pricing.money(c["paid_total"]), size=13, weight=ft.FontWeight.W_600))
        selected = c["id"] == self.selected_customer_id
        return theme.card(
            ft.Row([
                ft.CircleAvatar(content=ft.Text((c["name"] or "?")[:1].upper()), radius=18),
                ft.Column([
                    ft.Text(c["name"], weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(c["contact"] or "без контакта", size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0, expand=True, tight=True),
                ft.Column(right, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END, tight=True),
            ], spacing=12),
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            border=ft.border.all(2 if selected else 1, ft.Colors.PRIMARY if selected else ft.Colors.OUTLINE_VARIANT),
            on_click=lambda e, cid=c["id"]: self._open_customer(cid), ink=True,
        )

    def _open_customer(self, customer_id: int) -> None:
        self.selected_customer_id = customer_id
        self.refresh()

    def _close_customer(self) -> None:
        self.selected_customer_id = None
        self.detail_card.visible = False
        self.refresh(from_sync=True)

    def _render_detail(self, customer_id: int, from_sync: bool = False) -> None:
        customer = db.get_customer(customer_id)
        if not customer:
            self.detail_card.visible = False
            self.selected_customer_id = None
            return
        if from_sync and self.detail_column.controls and self._name_field is not None:
            # Поля с сохранением по on_blur: во время live-sync переиспользуем
            # текущие контролы, чтобы не затереть незасохранённый ввод.
            notes_field = self._notes_field
            name_field = self._name_field
            contact_field = self._contact_field
        else:
            name_field = theme.field("Имя", {"xs": 12, "md": 6}, value=customer["name"],
                                     on_blur=lambda e, cid=customer_id: self._save_identity(cid))
            contact_field = theme.field("Контакт", {"xs": 12, "md": 6}, value=customer["contact"] or "",
                                        on_blur=lambda e, cid=customer_id: self._save_identity(cid))
            notes_field = theme.field(
                "Заметки", {"xs": 12}, value=customer["notes"] or "", multiline=True, min_lines=2,
                on_blur=lambda e, cid=customer_id: db.update_customer(cid, notes=notes_field.value),
            )
            self._name_field = name_field
            self._contact_field = contact_field
            self._notes_field = notes_field

        orders = [o for o in db.list_orders("all", limit=500) if o["customer_id"] == customer_id]
        paid = sum(o["price"] or 0 for o in orders if o["paid"])
        debt = sum(o["price"] or 0 for o in orders if not o["paid"] and o["status"] != "cancelled")
        history = [self._history_row(o) for o in orders] or [
            ft.Text("Заказов пока нет.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        ]

        title_row = [ft.Text(customer["name"], size=20, weight=ft.FontWeight.W_700, expand=True)]
        if self.compact:
            title_row.insert(0, ft.IconButton(ft.Icons.ARROW_BACK, tooltip="К списку",
                                              on_click=lambda e: self._close_customer()))
        title_row.append(ft.OutlinedButton(
            "Удалить клиента", icon=ft.Icons.DELETE_OUTLINE,
            on_click=lambda e, cid=customer_id, n=len(orders): self._confirm_delete(cid, n),
            style=ft.ButtonStyle(color=ft.Colors.RED),
        ))

        self.detail_card.visible = True
        self.detail_column.controls = [
            ft.Row(title_row),
            theme.grid([
                self._stat("Заказов", str(len(orders))),
                self._stat("Оплачено", pricing.money(paid)),
                self._stat("Долг", pricing.money(debt), ft.Colors.RED_400 if debt else None),
            ]),
            theme.grid([name_field, contact_field, notes_field]),
            ft.Text("История заказов", size=15, weight=ft.FontWeight.W_600),
            *history,
        ]

    def _stat(self, label: str, value: str, color=None) -> ft.Control:
        return ft.Container(
            ft.Column([ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                       ft.Text(value, size=17, weight=ft.FontWeight.W_700, color=color)], spacing=2, tight=True),
            padding=12, border_radius=12, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            col={"xs": 12, "sm": 4},
        )

    def _history_row(self, o) -> ft.Control:
        return ft.Container(
            ft.Row([
                ft.Text(f"#{o['id']}", weight=ft.FontWeight.W_600, width=48),
                ft.Text(o["description"] or o["material"] or "", expand=True, size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                theme.status_chip(o["status"]),
                ft.Text(pricing.money(o["price"]), weight=ft.FontWeight.W_600, width=90,
                        text_align=ft.TextAlign.RIGHT),
            ], spacing=10),
            padding=ft.padding.symmetric(horizontal=10, vertical=8), border_radius=10,
            on_click=(lambda e, oid=o["id"]: self.on_open_order(oid)) if self.on_open_order else None,
            ink=bool(self.on_open_order), tooltip="Открыть заказ" if self.on_open_order else None,
        )

    def _save_identity(self, customer_id: int) -> None:
        customer = db.get_customer(customer_id)
        name = (self._name_field.value or "").strip()
        contact = (self._contact_field.value or "").strip()
        if customer and name == customer["name"] and contact == (customer["contact"] or ""):
            return
        try:
            db.rename_customer(customer_id, name, contact)
        except ValueError as exc:
            self._name_field.error_text = str(exc)
            self.update()
            return
        self._name_field.error_text = None
        self.refresh(from_sync=True)  # обновить список и заголовок, не пересоздавая поля ввода

    def _confirm_delete(self, customer_id: int, orders_count: int) -> None:
        customer = db.get_customer(customer_id)
        delete_orders_cb = ft.Checkbox(label=f"Удалить также его заказы ({orders_count})", value=False)

        def confirm(e: ft.ControlEvent) -> None:
            self.page.close(dialog)
            self._delete_customer(customer_id, delete_orders=bool(delete_orders_cb.value))

        dialog = ft.AlertDialog(
            title=ft.Text(f"Удалить клиента «{customer['name']}»?"),
            content=ft.Column([
                ft.Text("Если заказы не удалять, они останутся в списке заказов, но без привязки к клиенту."),
                delete_orders_cb,
            ], tight=True),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: self.page.close(dialog)),
                ft.TextButton("Удалить", on_click=confirm, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
        )
        self.page.open(dialog)

    def _delete_customer(self, customer_id: int, delete_orders: bool) -> None:
        db.delete_customer(customer_id, delete_orders=delete_orders)
        self.selected_customer_id = None
        self.detail_card.visible = False
        self.refresh()
