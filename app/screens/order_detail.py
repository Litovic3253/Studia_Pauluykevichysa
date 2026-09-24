"""Экран карточки заказа: просмотр/редактирование, статус, оплата, вложения."""
import shutil
from pathlib import Path
from typing import Callable

import flet as ft
import httpx

import db
import pricing
from app import theme
from app.telegram_files import TelegramFileError, download_file

LOCAL_STORAGE = Path(__file__).resolve().parent.parent / "files_storage"


class OrderDetailScreen(ft.Column):
    def __init__(self, order_id: int, on_back: Callable[[], None]):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.order_id = order_id
        self.on_back = on_back

        self.status_dd = ft.Dropdown(
            label="Статус",
            options=[ft.dropdown.Option(code, label) for code, label in db.STATUSES.items()],
            on_change=self._on_status_change,
        )
        self.paid_switch = ft.Switch(label="Оплачен", on_change=self._on_paid_change)
        self.client_field = ft.TextField(label="Клиент", on_blur=self._on_client_blur)
        self.contact_field = ft.TextField(label="Контакт", on_blur=self._on_client_blur)
        self.customer_dd = ft.Dropdown(label="Привязан к клиенту", on_change=self._on_customer_change)
        self.material_field = ft.TextField(label="Материал", on_blur=self._on_price_fields_blur)
        self.color_field = ft.TextField(label="Цвет", on_blur=self._on_other_field_blur, value="")
        self.weight_field = ft.TextField(label="Вес, г", on_blur=self._on_price_fields_blur)
        self.hours_field = ft.TextField(label="Часы печати", on_blur=self._on_price_fields_blur)
        self.qty_field = ft.TextField(label="Кол-во", on_blur=self._on_price_fields_blur)
        self.deadline_field = ft.TextField(label="Срок (ГГГГ-ММ-ДД)", on_blur=self._on_deadline_blur)
        self.price_field = ft.TextField(label="Цена (можно задать вручную)", on_blur=self._on_price_manual_blur)
        self.notes_field = ft.TextField(label="Заметки", multiline=True, on_blur=self._on_other_field_blur)
        self.price_text = ft.Text()
        self.attachments_column = ft.Column(spacing=4)

        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.status_banner = ft.Text("", color=ft.Colors.RED)

        self.controls = [
            ft.Row([ft.TextButton("← К списку", on_click=lambda e: self.on_back()), self.status_banner]),
            ft.Text(f"Заказ #{order_id}", size=20, weight=ft.FontWeight.BOLD),
            theme.card(ft.Column([
                ft.Row([self.status_dd, self.paid_switch]),
                ft.Row([self.client_field, self.contact_field]),
                self.customer_dd,
            ], spacing=theme.SPACING)),
            theme.card(ft.Column([
                ft.Row([self.material_field, self.color_field]),
                ft.Row([self.weight_field, self.hours_field, self.qty_field]),
                ft.Row([self.deadline_field, self.price_field]),
                self.price_text,
                self.notes_field,
            ], spacing=theme.SPACING)),
            theme.card(ft.Column([
                ft.Text("Вложения", weight=ft.FontWeight.BOLD),
                self.attachments_column,
                ft.ElevatedButton("Добавить файл", icon=ft.Icons.UPLOAD_FILE, on_click=self._on_add_file_click),
            ], spacing=theme.SPACING)),
            ft.OutlinedButton("Удалить заказ", icon=ft.Icons.DELETE, on_click=self._on_delete_click,
                               style=ft.ButtonStyle(color=ft.Colors.RED)),
        ]
        self._loaded = False

    def did_mount(self) -> None:
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)
            self.page.update()
        self.refresh()

    def will_unmount(self) -> None:
        if self.file_picker in self.page.overlay:
            self.page.overlay.remove(self.file_picker)

    def refresh(self, from_sync: bool = False) -> None:
        order = db.get_order(self.order_id)
        if not order:
            self.on_back()
            return

        if not from_sync:
            # Текстовые поля коммитятся только по on_blur — при live-sync тике их
            # нельзя перезаписывать, иначе теряется незасохранённый ввод пользователя.
            self.client_field.value = order["client"] or ""
            self.contact_field.value = order["contact"] or ""
            self.material_field.value = order["material"] or ""
            self.color_field.value = order["color"] or ""
            self.weight_field.value = str(order["weight_g"] or 0)
            self.hours_field.value = str(order["print_hours"] or 0)
            self.qty_field.value = str(order["qty"] or 1)
            self.deadline_field.value = order["deadline"] or ""
            self.price_field.value = str(order["price"] or 0)
            self.notes_field.value = order["notes"] or ""

        # Dropdown/Switch коммитятся сразу через on_change, поэтому их можно
        # безопасно обновлять и во время live-sync.
        self.status_dd.value = order["status"]
        self.paid_switch.value = bool(order["paid"])
        self.price_text.value = (
            f"Себестоимость: {pricing.money(order['cost'])} · Цена: {pricing.money(order['price'])}"
        )

        customers = db.list_customers()
        self.customer_dd.options = [ft.dropdown.Option(str(c["id"]), c["name"]) for c in customers]
        self.customer_dd.value = str(order["customer_id"]) if order["customer_id"] else None

        self.attachments_column.controls = [self._attachment_row(a) for a in db.list_attachments(self.order_id)] or [
            ft.Text("Вложений нет.", italic=True)
        ]

        if self.page:
            self.update()

    def _attachment_row(self, a) -> ft.Control:
        label = a["filename"] or a["file_id"] or f"вложение #{a['id']}"
        actions = [ft.IconButton(ft.Icons.DELETE, on_click=lambda e, aid=a["id"]: self._delete_attachment(aid))]
        if a["source"] == "telegram":
            actions.insert(
                0, ft.IconButton(ft.Icons.DOWNLOAD, on_click=lambda e, aid=a["id"]: self._download_attachment(aid))
            )
        else:
            actions.insert(0, ft.IconButton(ft.Icons.FOLDER_OPEN, on_click=lambda e, p=a["local_path"]: self._open_path(p)))
        return ft.Row([ft.Text(f"📎 {label} ({a['source']})", expand=True), *actions])

    def _open_path(self, path: str) -> None:
        import os
        try:
            os.startfile(path)  # noqa: S606 - открытие локального файла по клику пользователя
        except OSError as exc:
            self.status_banner.color = ft.Colors.RED
            self.status_banner.value = f"Не удалось открыть файл: {exc}"
            self.update()

    def _download_attachment(self, attachment_id: int) -> None:
        attachment = db.get_attachment(attachment_id)
        try:
            path = download_file(attachment["file_id"])
        except (TelegramFileError, httpx.HTTPError, OSError) as exc:
            self.status_banner.color = ft.Colors.RED
            self.status_banner.value = str(exc)
            self.update()
            return
        self.status_banner.color = None
        self.status_banner.value = f"Скачано: {path}"
        self.update()

    def _delete_attachment(self, attachment_id: int) -> None:
        db.delete_attachment(attachment_id)
        self.refresh()

    def _on_add_file_click(self, e: ft.ControlEvent) -> None:
        self.file_picker.pick_files(allow_multiple=True)

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        dest_dir = LOCAL_STORAGE / str(self.order_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in e.files:
            dest = dest_dir / f.name
            shutil.copy(f.path, dest)
            db.add_attachment(
                self.order_id, "local", local_path=str(dest), filename=f.name,
                file_type="document",
            )
        self.refresh()

    def _on_status_change(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, status=self.status_dd.value)
        self.refresh()

    def _on_paid_change(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, paid=1 if self.paid_switch.value else 0)

    def _on_client_blur(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, client=self.client_field.value, contact=self.contact_field.value)
        self.refresh()

    def _on_customer_change(self, e: ft.ControlEvent) -> None:
        value = self.customer_dd.value
        db.update_order(self.order_id, customer_id=int(value) if value else None)

    def _on_other_field_blur(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, color=self.color_field.value, notes=self.notes_field.value)

    def _on_deadline_blur(self, e: ft.ControlEvent) -> None:
        parsed = pricing.parse_date(self.deadline_field.value) or self.deadline_field.value or None
        db.update_order(self.order_id, deadline=parsed)
        self.refresh()

    def _on_price_manual_blur(self, e: ft.ControlEvent) -> None:
        value = pricing.parse_number(self.price_field.value)
        if value is not None:
            db.update_order(self.order_id, price=value)
            self.refresh()

    def _on_price_fields_blur(self, e: ft.ControlEvent) -> None:
        weight = pricing.parse_number(self.weight_field.value) or 0
        hours = pricing.parse_number(self.hours_field.value) or 0
        qty = int(pricing.parse_number(self.qty_field.value) or 1)
        db.update_order(
            self.order_id, material=self.material_field.value, weight_g=weight,
            print_hours=hours, qty=qty,
        )
        pricing.recalc_order_price(self.order_id)
        self.refresh()

    def _on_delete_click(self, e: ft.ControlEvent) -> None:
        def confirm(e2: ft.ControlEvent) -> None:
            self.page.close(dialog)
            db.delete_order(self.order_id)
            self.on_back()

        def cancel(e2: ft.ControlEvent) -> None:
            self.page.close(dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Удалить заказ?"),
            content=ft.Text(f"Заказ #{self.order_id} будет удалён без возможности восстановить."),
            actions=[ft.TextButton("Отмена", on_click=cancel), ft.TextButton("Удалить", on_click=confirm)],
        )
        self.page.open(dialog)
