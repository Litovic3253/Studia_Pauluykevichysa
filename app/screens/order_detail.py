"""Экран карточки заказа: слева клиент и параметры печати, справа статус, расчёт цены и вложения
(на узком окне — одной колонкой)."""
import shutil
from pathlib import Path
from typing import Callable

import flet as ft

import db
import pricing
from paths import DATA_DIR
from app import input_hints, plastics, price_view, theme
from app.dialogs import grams_dialog

LOCAL_STORAGE = DATA_DIR / "files_storage"

FILE_ICONS = {".stl": ft.Icons.VIEW_IN_AR, ".3mf": ft.Icons.VIEW_IN_AR, ".obj": ft.Icons.VIEW_IN_AR,
              ".png": ft.Icons.IMAGE, ".jpg": ft.Icons.IMAGE, ".jpeg": ft.Icons.IMAGE, ".pdf": ft.Icons.PICTURE_AS_PDF}


def resolve_attachment_path(a) -> Path:
    """Путь к локальному вложению. В базе путь абсолютный — после переноса папки
    с программой на другой компьютер он «битый», поэтому ищем файл заново
    в files_storage/<номер заказа>/ рядом с программой."""
    stored = Path(a["local_path"])
    if stored.exists():
        return stored
    fallback = LOCAL_STORAGE / str(a["order_id"]) / (a["filename"] or stored.name)
    return fallback if fallback.exists() else stored


class OrderDetailScreen(ft.Column):
    def __init__(self, order_id: int, on_back: Callable[[], None]):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.order_id = order_id
        self.on_back = on_back

        half = {"xs": 12, "md": 6}
        third = {"xs": 12, "sm": 6, "md": 4}

        self.status_dd = theme.dropdown(
            "Статус", width=210,
            options=[ft.dropdown.Option(code, theme.status_style(code)[0]) for code in db.STATUSES],
            on_change=self._on_status_change,
        )
        self.paid_switch = ft.Switch(label="Оплачен", on_change=self._on_paid_change)
        self.client_field = theme.field("Клиент", half, on_blur=self._on_client_blur)
        self.contact_field = theme.field("Контакт", half, on_blur=self._on_client_blur)
        self.customer_dd = theme.dropdown("Карточка клиента", width=300, on_change=self._on_customer_change)
        self.material_field = theme.dropdown("Материал", on_change=self._on_price_fields_blur)
        self.color_field = theme.field("Цвет", half, on_blur=self._on_other_field_blur, value="")
        self.weight_field = input_hints.weight_field(
            on_blur=self._on_price_fields_blur, on_pick=lambda: self._on_price_fields_blur(None), col=half,
        )
        self.hours_field = input_hints.hours_field(
            on_blur=self._on_price_fields_blur, on_pick=lambda: self._on_price_fields_blur(None), col=half,
        )
        self.qty_field = theme.field("Кол-во, шт", third, on_blur=self._on_price_fields_blur)
        self.defect_field = theme.field("Брак, %", third, helper_text="от цены печати",
                                        on_blur=self._on_price_fields_blur)
        self.deadline_field = theme.field("Срок", third, hint_text="дд.мм.гггг", helper_text="или «завтра»",
                                          on_blur=self._on_deadline_blur)
        self.notes_field = theme.field("Заметки", {"xs": 12}, multiline=True, min_lines=2,
                                       on_blur=self._on_other_field_blur)
        self.price_field = theme.field("Итоговая цена", {"xs": 12}, helper_text="Можно задать вручную",
                                       on_blur=self._on_price_manual_blur)
        self.breakdown_column = ft.Column(spacing=6)
        self.manual_price_note = ft.Text("", size=12, color=ft.Colors.ORANGE_800, visible=False)
        self.attachments_column = ft.Column(spacing=4)
        self.usage_row = ft.Row(spacing=8, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.status_banner = ft.Text("", color=ft.Colors.RED, visible=False)
        self.header = ft.Container()

        left = ft.Column([
            theme.section("Клиент", [theme.grid([self.client_field, self.contact_field,
                                                 theme.in_col(self.customer_dd, {"xs": 12})])],
                          icon=ft.Icons.PERSON_OUTLINE),
            theme.section("Печать", [theme.grid([
                theme.in_col(self.material_field, half), self.color_field, self.weight_field, self.hours_field,
                self.qty_field, self.defect_field, self.deadline_field, self.notes_field,
            ]), ft.Divider(height=4), self.usage_row], icon=ft.Icons.PRECISION_MANUFACTURING),
        ], spacing=theme.SPACING, col={"xs": 12, "lg": 7})

        right = ft.Column([
            theme.section("Статус и оплата", [ft.Row([self.status_dd, self.paid_switch], spacing=16, wrap=True)],
                          icon=ft.Icons.FLAG_OUTLINED),
            theme.section("Расчёт цены", [self.breakdown_column, self.manual_price_note,
                                          theme.grid([self.price_field])],
                          icon=ft.Icons.CALCULATE_OUTLINED),
            theme.section("Вложения", [
                self.attachments_column,
                ft.OutlinedButton("Добавить файл", icon=ft.Icons.ATTACH_FILE, on_click=self._on_add_file_click),
            ], icon=ft.Icons.FOLDER_OPEN),
        ], spacing=theme.SPACING, col={"xs": 12, "lg": 5})

        self.controls = [self.header, self.status_banner, theme.grid([left, right])]
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

        self.header.content = theme.page_header(
            f"Заказ #{self.order_id} · {order['client']}",
            f"создан {pricing.fmt_date(order['created_at'][:10])}",
            [ft.OutlinedButton("Удалить заказ", icon=ft.Icons.DELETE_OUTLINE, on_click=self._on_delete_click,
                               style=ft.ButtonStyle(color=ft.Colors.RED))],
            leading=ft.IconButton(ft.Icons.ARROW_BACK, tooltip="К списку", on_click=lambda e: self.on_back()),
        )

        materials = list(db.get_settings()["materials"])
        if order["material"] and order["material"] not in materials:
            materials.append(order["material"])  # материал удалён из «Цен», но в заказе он остался
        self.material_field.options = [ft.dropdown.Option(m) for m in materials]

        if not from_sync:
            # Текстовые поля коммитятся только по on_blur — при live-sync тике их
            # нельзя перезаписывать, иначе теряется незасохранённый ввод пользователя.
            self.client_field.value = order["client"] or ""
            self.contact_field.value = order["contact"] or ""
            self.material_field.value = order["material"]
            self.color_field.value = order["color"] or ""
            self.weight_field.value = pricing.fmt_number(order["weight_g"])
            self.hours_field.value = pricing.fmt_hours(order["print_hours"])
            input_hints.check_weight(self.weight_field)
            input_hints.check_hours(self.hours_field)
            self.qty_field.value = str(order["qty"] or 1)
            self.defect_field.value = pricing.fmt_number(order["defect_percent"])
            self.deadline_field.value = pricing.fmt_date(order["deadline"]) if order["deadline"] else ""
            self.deadline_field.error_text = None
            self.price_field.value = pricing.fmt_number(order["price"])
            self.notes_field.value = order["notes"] or ""

        # Dropdown/Switch коммитятся сразу через on_change, поэтому их можно
        # безопасно обновлять и во время live-sync.
        self.status_dd.value = order["status"]
        self.paid_switch.value = bool(order["paid"])

        calc = pricing.calc_price(order["material"], order["weight_g"] or 0, order["print_hours"] or 0,
                                  order["qty"] or 1, bool(order["reverse_engineering"]), order["defect_percent"] or 0)
        self.breakdown_column.controls = price_view.breakdown_rows(calc, order["defect_percent"] or 0,
                                                                   total=order["price"])
        manual = abs((order["price"] or 0) - calc["price"]) >= 1
        self.manual_price_note.visible = manual
        self.manual_price_note.value = f"Цена задана вручную (по расчёту — {pricing.money(calc['price'])})"

        customers = db.list_customers()
        self.customer_dd.options = [ft.dropdown.Option(str(c["id"]), c["name"]) for c in customers]
        self.customer_dd.value = str(order["customer_id"]) if order["customer_id"] else None

        self._render_usage(order)

        self.attachments_column.controls = [self._attachment_row(a) for a in db.list_attachments(self.order_id)] or [
            ft.Text("Файлов пока нет.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        ]

        if self.page:
            self.update()

    # ---------- списание пластика ----------

    def _render_usage(self, order) -> None:
        usage = db.order_usage(self.order_id)
        if usage:
            where = usage["plastic"] + (f" · {usage['color']}" if usage["color"] else "")
            self.usage_row.controls = [
                theme.pill(f"Списано {pricing.fmt_number(usage['grams'])} г с {where}", ft.Colors.GREEN,
                           ft.Icons.CHECK_CIRCLE),
                ft.TextButton("Отменить списание", icon=ft.Icons.UNDO,
                              on_click=lambda e, uid=usage["id"]: self._undo_usage(uid)),
            ]
        else:
            planned = (order["weight_g"] or 0) * (order["qty"] or 1)
            self.usage_row.controls = [
                ft.Text(f"Пластик для заказа: {pricing.fmt_number(planned)} г", size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
                ft.FilledTonalButton("Списать пластик", icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                     on_click=lambda e: self._ask_write_off()),
            ]

    def spools_for_order(self) -> list:
        """Активные катушки с остатком; подходящие к материалу заказа — первыми."""
        order = db.get_order(self.order_id)
        family = plastics.family(order["material"])
        spools = [s for s in db.list_spools() if s["remaining_g"] > 0]
        return sorted(spools, key=lambda s: (plastics.family(s["plastic"]) != family, s["plastic"], s["id"]))

    def _ask_write_off(self) -> None:
        spools = self.spools_for_order()
        if not spools:
            self.page.open(ft.SnackBar(ft.Text("Нет катушек с остатком — добавьте катушку в «Калькуляторе пластика».")))
            return
        order = db.get_order(self.order_id)
        spool_dd = theme.dropdown("Катушка", width=380, value=str(spools[0]["id"]), options=[
            ft.dropdown.Option(str(s["id"]), f"{s['plastic']}{' · ' + s['color'] if s['color'] else ''}"
                                             f" — осталось {pricing.fmt_number(s['remaining_g'])} г")
            for s in spools
        ])
        planned = (order["weight_g"] or 0) * (order["qty"] or 1)

        def ok(grams: float) -> None:
            self.write_off(int(spool_dd.value), grams)

        grams_dialog(self.page, f"Списать пластик · заказ #{self.order_id}", "Сколько граммов",
                     pricing.fmt_number(planned) if planned else "", ok,
                     helper="Подставлено: вес × количество из заказа", extra=[spool_dd])

    def write_off(self, spool_id: int, grams: float) -> None:
        try:
            db.use_spool(spool_id, grams, order_id=self.order_id)
        except ValueError as exc:
            if self.page:
                self.page.open(ft.SnackBar(ft.Text(str(exc))))
        self.refresh()

    def _undo_usage(self, usage_id: int) -> None:
        db.undo_usage(usage_id)
        self.refresh()

    def _attachment_row(self, a) -> ft.Control:
        label = a["filename"] or a["file_id"] or f"вложение #{a['id']}"
        icon = FILE_ICONS.get(Path(label).suffix.lower(), ft.Icons.INSERT_DRIVE_FILE_OUTLINED)
        actions = [ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Удалить файл",
                                 on_click=lambda e, aid=a["id"]: self._delete_attachment(aid))]
        if a["local_path"]:
            actions.insert(0, ft.IconButton(ft.Icons.OPEN_IN_NEW, tooltip="Открыть",
                                            on_click=lambda e, a=a: self._open_path(str(resolve_attachment_path(a)))))
        return ft.Row([
            ft.Icon(icon, size=20, color=ft.Colors.PRIMARY),
            ft.Text(label, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=label),
            *actions,
        ], spacing=8)

    def _open_path(self, path: str) -> None:
        import os
        try:
            os.startfile(path)  # noqa: S606 - открытие локального файла по клику пользователя
        except OSError as exc:
            self.status_banner.color = ft.Colors.RED
            self.status_banner.value = f"Не удалось открыть файл: {exc}"
            self.status_banner.visible = True
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
        text = (self.deadline_field.value or "").strip()
        parsed = pricing.parse_date(text) if text else None
        if text and not parsed:
            self.deadline_field.error_text = "Не понял дату. Пример: 25.10.2026 или «завтра»"
            self.update()
            return
        self.deadline_field.error_text = None
        db.update_order(self.order_id, deadline=parsed)
        self.refresh()

    def _on_price_manual_blur(self, e: ft.ControlEvent) -> None:
        value = pricing.parse_number(self.price_field.value)
        if value is not None:
            db.update_order(self.order_id, price=value)
            self.refresh()

    def _on_price_fields_blur(self, e: ft.ControlEvent | None) -> None:
        weight = input_hints.check_weight(self.weight_field)
        hours = input_hints.check_hours(self.hours_field)
        if weight is None or hours is None:
            self.update()  # показать ошибку у поля; в базу неразобранное значение не пишем
            return
        qty = int(pricing.parse_number(self.qty_field.value) or 1)
        defect = pricing.parse_number(self.defect_field.value) or 0
        db.update_order(
            self.order_id, material=self.material_field.value, weight_g=weight,
            print_hours=hours, qty=qty, defect_percent=defect,
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
            actions=[ft.TextButton("Отмена", on_click=cancel),
                     ft.TextButton("Удалить", on_click=confirm, style=ft.ButtonStyle(color=ft.Colors.RED))],
        )
        self.page.open(dialog)
