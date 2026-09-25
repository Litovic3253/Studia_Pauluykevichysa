"""Экран «Новый заказ»: слева форма (клиент, печать, файлы), справа блок «Итого» с разбивкой цены
(на узком окне — под формой)."""
import shutil
from typing import Callable

import flet as ft

import db
import pricing
from paths import DATA_DIR
from app import input_hints, price_view, theme

LOCAL_STORAGE = DATA_DIR / "files_storage"


class NewOrderScreen(ft.Column):
    def __init__(self, on_created: Callable[[int], None]):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.on_created = on_created
        self._picked_files: list = []

        half = {"xs": 12, "md": 6}
        third = {"xs": 12, "sm": 6, "md": 4}

        self.client_field = theme.field("Клиент *", half)
        self.contact_field = theme.field("Контакт", half, hint_text="телефон, @ник, авито…")
        self.description_field = theme.field("Описание", {"xs": 12}, multiline=True, min_lines=2)
        self.material_dd = theme.dropdown("Материал", on_change=self._recalc)
        self.color_field = theme.field("Цвет", half)
        self.weight_field = input_hints.weight_field(
            value="0", on_change=self._recalc, on_pick=lambda: self._recalc(None), col=half,
        )
        self.hours_field = input_hints.hours_field(
            value="0", on_change=self._recalc, on_pick=lambda: self._recalc(None), col=half,
        )
        self.qty_field = theme.field("Кол-во, шт", third, value="1", on_change=self._recalc)
        self.defect_field = theme.field(
            "Брак, %", third, value=pricing.fmt_number(db.get_settings()["defect_percent"]),
            helper_text="от цены печати", on_change=self._recalc,
        )
        self.deadline_field = theme.field("Срок", third, hint_text="дд.мм.гггг", helper_text="или «завтра»")
        self.reverse_checkbox = ft.Checkbox(label="Реверс-моделирование (у клиента нет 3D-модели)",
                                            on_change=self._recalc)
        self.breakdown_column = ft.Column(spacing=6)
        self.custom_price_field = theme.field("Своя цена", {"xs": 12}, helper_text="Необязательно — вместо расчётной")
        self.files_text = ft.Text("Файлы не выбраны.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.error_text = ft.Text("", color=ft.Colors.RED)

        form = ft.Column([
            theme.section("Клиент", [theme.grid([self.client_field, self.contact_field, self.description_field])],
                          icon=ft.Icons.PERSON_OUTLINE),
            theme.section("Печать", [
                theme.grid([theme.in_col(self.material_dd, half), self.color_field, self.weight_field, self.hours_field,
                            self.qty_field, self.defect_field, self.deadline_field]),
                self.reverse_checkbox,
            ], icon=ft.Icons.PRECISION_MANUFACTURING),
            theme.section("Файлы", [
                ft.Row([ft.OutlinedButton("Прикрепить файлы", icon=ft.Icons.ATTACH_FILE,
                                          on_click=lambda e: self.file_picker.pick_files(allow_multiple=True)),
                        ft.Container(self.files_text, expand=True)], wrap=True),
            ], icon=ft.Icons.FOLDER_OPEN),
        ], spacing=theme.SPACING, col={"xs": 12, "lg": 8})

        summary = theme.section("Итого", [
            self.breakdown_column,
            theme.grid([self.custom_price_field]),
            self.error_text,
            ft.FilledButton("Создать заказ", icon=ft.Icons.CHECK, on_click=self._on_save,
                            style=ft.ButtonStyle(padding=18), width=10_000),
        ], icon=ft.Icons.CALCULATE_OUTLINED, col={"xs": 12, "lg": 4})

        self.controls = [
            theme.page_header("Новый заказ", "Цена считается сама по мере заполнения"),
            theme.grid([form, summary]),
        ]

    def did_mount(self) -> None:
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)
        settings = db.get_settings()
        self.material_dd.options = [ft.dropdown.Option(m) for m in settings["materials"]]
        if not self._picked_files and not (self.client_field.value or "").strip():
            # Пустая форма — подхватить процент брака, если его поменяли в «Ценах».
            self.defect_field.value = pricing.fmt_number(settings["defect_percent"])
        self.page.update()
        self._recalc(None)

    def will_unmount(self) -> None:
        if self.file_picker in self.page.overlay:
            self.page.overlay.remove(self.file_picker)

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        self._picked_files = list(e.files or [])
        self.files_text.value = ", ".join(f.name for f in self._picked_files) or "Файлы не выбраны."
        self.update()

    def _recalc(self, e: ft.ControlEvent | None) -> None:
        weight = input_hints.check_weight(self.weight_field) or 0
        hours = input_hints.check_hours(self.hours_field) or 0
        qty = int(pricing.parse_number(self.qty_field.value) or 1)
        defect = pricing.parse_number(self.defect_field.value) or 0
        result = pricing.calc_price(
            self.material_dd.value, weight, hours, qty, bool(self.reverse_checkbox.value), defect
        )
        self.breakdown_column.controls = price_view.breakdown_rows(result, defect)
        if self.page:
            self.update()

    def _on_save(self, e: ft.ControlEvent) -> None:
        if not (self.client_field.value or "").strip():
            self.error_text.value = "Укажите клиента."
            self.update()
            return

        weight = input_hints.check_weight(self.weight_field)
        hours = input_hints.check_hours(self.hours_field)
        if weight is None or hours is None:
            self.error_text.value = "Проверьте вес и часы печати — формат не распознан (см. подсказку ⓘ у поля)."
            self.update()
            return
        deadline_text = (self.deadline_field.value or "").strip()
        deadline = pricing.parse_date(deadline_text) if deadline_text else None
        if deadline_text and not deadline:
            self.deadline_field.error_text = "Не понял дату. Пример: 25.10.2026 или «завтра»"
            self.error_text.value = "Проверьте срок."
            self.update()
            return
        self.deadline_field.error_text = None
        qty = int(pricing.parse_number(self.qty_field.value) or 1)
        reverse = bool(self.reverse_checkbox.value)
        defect = pricing.parse_number(self.defect_field.value) or 0
        calc = pricing.calc_price(self.material_dd.value, weight, hours, qty, reverse, defect)
        custom_price = pricing.parse_number(self.custom_price_field.value)
        price = custom_price if custom_price is not None else calc["price"]

        order_id = db.add_order({
            "client": self.client_field.value.strip(),
            "contact": self.contact_field.value or "",
            "description": self.description_field.value or "",
            "material": self.material_dd.value,
            "color": self.color_field.value or "",
            "weight_g": weight,
            "print_hours": hours,
            "qty": qty,
            "deadline": deadline,
            "cost": round(calc["cost"], 2),
            "price": price,
            "notes": "",
            "reverse_engineering": 1 if reverse else 0,
            "defect_percent": defect,
        })

        dest_dir = LOCAL_STORAGE / str(order_id)
        for f in self._picked_files:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f.name
            shutil.copy(f.path, dest)
            db.add_attachment(order_id, "local", local_path=str(dest), filename=f.name, file_type="document")

        self._reset_form()
        self.on_created(order_id)

    def _reset_form(self) -> None:
        self.client_field.value = ""
        self.contact_field.value = ""
        self.description_field.value = ""
        self.color_field.value = ""
        self.weight_field.value = "0"
        self.hours_field.value = "0"
        self.qty_field.value = "1"
        self.defect_field.value = pricing.fmt_number(db.get_settings()["defect_percent"])
        self.deadline_field.value = ""
        self.reverse_checkbox.value = False
        self.custom_price_field.value = ""
        self.error_text.value = ""
        self._picked_files = []
        self.files_text.value = "Файлы не выбраны."
        self._recalc(None)
