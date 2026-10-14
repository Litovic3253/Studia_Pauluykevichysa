"""Экран «Новый заказ»: слева форма (клиент, печать, электроника, файлы), справа блок «Итого» с разбивкой
цены (на узком окне — под формой). Печать и электроника включаются переключателями — можно обе."""
import shutil
from typing import Callable

import flet as ft

import db
import pricing
from paths import DATA_DIR
from app import client_pdf, input_hints, price_view, theme
from app.components_editor import ComponentsEditor

LOCAL_STORAGE = DATA_DIR / "files_storage"


class NewOrderScreen(ft.Column):
    def __init__(self, on_created: Callable[[int], None]):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.on_created = on_created
        self._picked_files: list = []
        settings = db.get_settings()

        half = {"xs": 12, "md": 6}
        third = {"xs": 12, "sm": 6, "md": 4}

        self.client_field = theme.field("Клиент *", half)
        self.contact_field = theme.field("Контакт", half, hint_text="телефон, @ник, авито…")
        self.description_field = theme.field("Описание", {"xs": 12}, multiline=True, min_lines=2)
        self.material_dd = theme.dropdown("Материал", stretch=True, col=half, on_change=self._recalc)
        self.color_field = theme.field("Цвет", half)
        self.weight_field = input_hints.weight_field(
            value="0", on_change=self._recalc, on_pick=lambda: self._recalc(None), col=half,
        )
        self.hours_field = input_hints.hours_field(
            value="0", on_change=self._recalc, on_pick=lambda: self._recalc(None), col=half,
        )
        self.qty_field = theme.field("Кол-во, шт", half, value="1", on_change=self._recalc)
        self.defect_field = theme.field(
            "Брак, %", half, value=pricing.fmt_number(settings["defect_percent"]),
            helper_text="от цены печати", on_change=self._recalc,
        )
        self.deadline_field = input_hints.date_field("Срок", col=half, hint_text="дд.мм.гггг",
                                                     helper_text="или «завтра»")
        self.reverse_checkbox = ft.Checkbox(label="Реверс-моделирование (у клиента нет 3D-модели)",
                                            on_change=self._recalc)
        self.print_switch = ft.Switch(value=True, on_change=self._on_parts_change,
                                      tooltip=theme.tip("В заказе есть 3D-печать"))
        self.electronics_switch = ft.Switch(value=False, on_change=self._on_parts_change,
                                            tooltip=theme.tip("В заказе есть электроника"))
        self.components_editor = ComponentsEditor(on_change=lambda: self._recalc(None), live=True)
        self.markup_field = theme.field("Наценка на компоненты", third, suffix_text="%",
                                        value=pricing.fmt_number(settings["components_markup"]),
                                        on_change=self._recalc)
        self.soldering_field = theme.field("Пайка и сборка", third, suffix_text="₽", on_change=self._recalc)
        self.firmware_field = theme.field("Программирование (прошивка)", third, suffix_text="₽",
                                          on_change=self._recalc)
        self.print_body = ft.Column([
            theme.grid([self.material_dd, self.color_field, self.weight_field, self.hours_field,
                        self.qty_field, self.defect_field]),
            self.reverse_checkbox,
        ], spacing=14)
        self.electronics_body = ft.Column([
            ft.Text("На весь заказ: если устройств несколько — укажите компоненты на все.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            self.components_editor,
            theme.grid([self.markup_field, self.soldering_field, self.firmware_field]),
        ], spacing=14, visible=False)
        self.breakdown_column = ft.Column(spacing=6)
        self.profit_column = ft.Column(spacing=6)
        self.custom_price_field = theme.field("Своя цена", {"xs": 12}, helper_text="Необязательно — вместо расчётной",
                                              on_change=self._recalc)
        self.prepayment_field = theme.field("Предоплата", {"xs": 12}, suffix_text="₽",
                                            helper_text="Необязательно — можно внести позже в карточке заказа")
        self.files_text = ft.Text("Файлы не выбраны.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.error_text = ft.Text("", color=theme.ERR)

        form = ft.Column([
            theme.section("Клиент", [theme.grid([self.client_field, self.contact_field, self.description_field,
                                                 self.deadline_field])],
                          icon=ft.Icons.PERSON_OUTLINE),
            theme.section("Печать", [self.print_body], icon=ft.Icons.PRECISION_MANUFACTURING,
                          actions=[self.print_switch]),
            theme.section("Электроника", [self.electronics_body], icon=ft.Icons.MEMORY,
                          actions=[self.electronics_switch]),
            theme.section("Файлы", [
                ft.Row([ft.OutlinedButton("Прикрепить файлы", icon=ft.Icons.ATTACH_FILE,
                                          on_click=lambda e: self.file_picker.pick_files(allow_multiple=True)),
                        ft.Container(self.files_text, expand=True)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], icon=ft.Icons.FOLDER_OPEN),
        ], spacing=theme.SPACING, col={"xs": 12, "lg": 8})

        summary = theme.section("Итого", [
            self.breakdown_column,
            price_view.profit_box([self.profit_column]),
            theme.grid([self.custom_price_field, self.prepayment_field]),
            self.error_text,
            ft.FilledButton("Создать заказ", icon=ft.Icons.CHECK, on_click=self._on_save,
                            style=ft.ButtonStyle(padding=18), width=10_000),
        ], icon=ft.Icons.CALCULATE_OUTLINED, col={"xs": 12, "lg": 4})

        self.controls = [
            theme.page_header("Новый заказ", "Печать и/или электроника — цена считается сама"),
            theme.grid([form, summary]),
        ]

    def did_mount(self) -> None:
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)
        settings = db.get_settings()
        self.material_dd.options = [ft.dropdown.Option(m) for m in settings["materials"]]
        if not self._picked_files and not (self.client_field.value or "").strip():
            # Пустая форма — подхватить процент брака и наценку, если их поменяли в «Ценах».
            self.defect_field.value = pricing.fmt_number(settings["defect_percent"])
            self.markup_field.value = pricing.fmt_number(settings["components_markup"])
        self.components_editor.load_catalog()
        self.page.update()
        self._recalc(None)

    def will_unmount(self) -> None:
        if self.file_picker in self.page.overlay:
            self.page.overlay.remove(self.file_picker)

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        self._picked_files = list(e.files or [])
        self.files_text.value = ", ".join(f.name for f in self._picked_files) or "Файлы не выбраны."
        self.update()

    def _on_parts_change(self, e: ft.ControlEvent | None) -> None:
        self.print_body.visible = bool(self.print_switch.value)
        self.electronics_body.visible = bool(self.electronics_switch.value)
        self._recalc(None)

    def _calc(self, components: list[dict]) -> dict:
        has_print = bool(self.print_switch.value)
        weight = (input_hints.check_weight(self.weight_field) or 0) if has_print else 0
        hours = (input_hints.check_hours(self.hours_field) or 0) if has_print else 0
        return pricing.calc_price(
            self.material_dd.value, weight, hours, int(pricing.parse_number(self.qty_field.value) or 1),
            bool(self.reverse_checkbox.value), pricing.parse_number(self.defect_field.value) or 0,
            has_print=has_print, has_electronics=bool(self.electronics_switch.value),
            components=components, markup=pricing.parse_number(self.markup_field.value) or 0,
            soldering=pricing.parse_number(self.soldering_field.value) or 0,
            firmware=pricing.parse_number(self.firmware_field.value) or 0,
        )

    def _recalc(self, e: ft.ControlEvent | None) -> None:
        result = self._calc(self.components_editor.preview())
        defect = pricing.parse_number(self.defect_field.value) or 0
        custom_price = pricing.parse_number(self.custom_price_field.value)
        self.breakdown_column.controls = price_view.breakdown_rows(result, defect, total=custom_price)
        self.profit_column.controls = price_view.profit_rows(result, self.material_dd.value, total=custom_price)
        if self.page:
            self.update()

    def _on_save(self, e: ft.ControlEvent) -> None:
        if not (self.client_field.value or "").strip():
            self.error_text.value = "Укажите клиента."
            self.update()
            return
        has_print, has_el = bool(self.print_switch.value), bool(self.electronics_switch.value)
        if not (has_print or has_el):
            self.error_text.value = "Включите «Печать» или «Электронику»."
            self.update()
            return

        weight = input_hints.check_weight(self.weight_field) if has_print else 0
        hours = input_hints.check_hours(self.hours_field) if has_print else 0
        if weight is None or hours is None:
            self.error_text.value = "Проверьте вес и часы печати — формат не распознан (см. подсказку ⓘ у поля)."
            self.update()
            return
        components = self.components_editor.get_components() if has_el else []
        money_fields = [(self.markup_field, "наценка"), (self.soldering_field, "пайка"),
                        (self.firmware_field, "прошивка")] if has_el else []
        bad = [label for f, label in money_fields
               if (f.value or "").strip() and pricing.parse_number(f.value) is None]
        if components is None or bad:
            what = ", ".join(bad) if bad else "кол-во и цены компонентов"
            self.error_text.value = f"Проверьте электронику: {what} — нужны числа."
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
        reverse = bool(self.reverse_checkbox.value) and has_print
        defect = pricing.parse_number(self.defect_field.value) or 0
        calc = self._calc(components)
        custom_price = pricing.parse_number(self.custom_price_field.value)
        price = custom_price if custom_price is not None else calc["price"]
        prepayment_text = (self.prepayment_field.value or "").strip()
        prepayment = pricing.parse_number(prepayment_text)
        if prepayment_text and prepayment is None:
            self.error_text.value = "Предоплата — это сумма числом."
            self.update()
            return

        def el_number(field: ft.TextField) -> float:
            return (pricing.parse_number(field.value) or 0) if has_el else 0

        order_id = db.add_order({
            "client": self.client_field.value.strip(),
            "contact": self.contact_field.value or "",
            "description": self.description_field.value or "",
            "material": self.material_dd.value if has_print else None,
            "color": (self.color_field.value or "") if has_print else "",
            "weight_g": weight,
            "print_hours": hours,
            "qty": qty,
            "deadline": deadline,
            "cost": round(calc["cost"], 2),
            "price": price,
            "notes": "",
            "reverse_engineering": 1 if reverse else 0,
            "defect_percent": defect,
            "prepayment": prepayment or 0,
            "has_print": 1 if has_print else 0,
            "has_electronics": 1 if has_el else 0,
            "components_markup": el_number(self.markup_field),
            "soldering_price": el_number(self.soldering_field),
            "firmware_price": el_number(self.firmware_field),
        })
        if components:
            db.set_components(order_id, components)

        dest_dir = LOCAL_STORAGE / str(order_id)
        for f in self._picked_files:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f.name
            shutil.copy(f.path, dest)
            db.add_attachment(order_id, "local", local_path=str(dest), filename=f.name, file_type="document")

        # PDF для клиента — сразу после создания; ошибка PDF не мешает самому заказу.
        page = self.page
        try:
            pdf_path = client_pdf.build_order_pdf(order_id)
        except Exception as exc:  # noqa: BLE001 - покажем пользователю, заказ уже сохранён
            pdf_path, pdf_error = None, exc
        self._reset_form()
        self.on_created(order_id)
        if page and pdf_path:
            client_pdf.notify_saved(page, pdf_path)
        elif page:
            page.open(ft.SnackBar(ft.Text(f"Заказ создан, но PDF не сохранился: {pdf_error}"), bgcolor=theme.ERR))

    def _reset_form(self) -> None:
        settings = db.get_settings()
        self.client_field.value = ""
        self.contact_field.value = ""
        self.description_field.value = ""
        self.color_field.value = ""
        self.weight_field.value = "0"
        self.hours_field.value = "0"
        self.qty_field.value = "1"
        self.defect_field.value = pricing.fmt_number(settings["defect_percent"])
        self.deadline_field.value = ""
        self.reverse_checkbox.value = False
        self.print_switch.value = True
        self.electronics_switch.value = False
        self.print_body.visible, self.electronics_body.visible = True, False
        self.components_editor.set_components([])
        self.markup_field.value = pricing.fmt_number(settings["components_markup"])
        self.soldering_field.value = ""
        self.firmware_field.value = ""
        self.custom_price_field.value = ""
        self.prepayment_field.value = ""
        self.error_text.value = ""
        self._picked_files = []
        self.files_text.value = "Файлы не выбраны."
        self._recalc(None)
