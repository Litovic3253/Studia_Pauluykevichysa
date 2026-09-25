"""Экран «Цены»: редактирование материалов, ставки часа, реверс-цены, валюты."""
import flet as ft

import db
import pricing
from app import theme


class PricesScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.materials_column = ft.Column(spacing=4)
        self.new_material_name = ft.TextField(label="Материал (напр. PLA)", width=200)
        self.new_material_price = ft.TextField(label="Цена за кг", width=150)
        self.hour_rate_field = ft.TextField(label="Ставка часа печати", on_blur=self._save_scalars)
        self.reverse_price_field = ft.TextField(label="Реверс-моделирование", on_blur=self._save_scalars)
        self.currency_field = ft.TextField(label="Валюта", on_blur=self._save_scalars)
        self.defect_field = ft.TextField(
            label="Процент брака по умолчанию, %", on_blur=self._save_scalars,
            helper_text="Подставляется в новые заказы; в каждом заказе можно поменять",
        )
        self.status_text = ft.Text("")

        self.controls = [
            ft.Text("Цены и настройки", size=20, weight=ft.FontWeight.BOLD),
            theme.card(ft.Column([
                ft.Text("Материалы (₽/кг):", weight=ft.FontWeight.BOLD),
                self.materials_column,
                ft.Row([self.new_material_name, self.new_material_price,
                        ft.ElevatedButton("Добавить", on_click=self._add_material)]),
            ], spacing=theme.SPACING)),
            theme.card(ft.Column([
                self.hour_rate_field,
                self.reverse_price_field,
                self.defect_field,
                self.currency_field,
            ], spacing=theme.SPACING)),
            self.status_text,
        ]
        self.refresh()

    def refresh(self) -> None:
        settings = db.get_settings()
        self.materials_column.controls = [
            self._material_row(name, price) for name, price in settings["materials"].items()
        ] or [ft.Text("Материалов нет.", italic=True)]
        self.hour_rate_field.value = str(settings["hour_rate"])
        self.reverse_price_field.value = str(settings["reverse_price"])
        self.defect_field.value = pricing.fmt_number(settings["defect_percent"])
        self.currency_field.value = settings["currency"]
        if self.page:
            self.update()

    def _material_row(self, name: str, price: float) -> ft.Control:
        price_field = ft.TextField(value=str(price), width=120)

        def save(e: ft.ControlEvent) -> None:
            value = pricing.parse_number(price_field.value)
            if value is None:
                return
            settings = db.get_settings()
            settings["materials"][name] = value
            db.set_setting("materials", settings["materials"])
            self.status_text.value = f"Сохранено: {name}"
            self.update()

        def delete(e: ft.ControlEvent) -> None:
            settings = db.get_settings()
            settings["materials"].pop(name, None)
            db.set_setting("materials", settings["materials"])
            self.refresh()

        price_field.on_blur = save
        return ft.Row([ft.Text(name, width=100), price_field, ft.IconButton(ft.Icons.DELETE, on_click=delete)])

    def _add_material(self, e: ft.ControlEvent) -> None:
        name = (self.new_material_name.value or "").strip()
        value = pricing.parse_number(self.new_material_price.value)
        if not name or value is None:
            self.status_text.value = "Укажите название материала и цену."
            self.update()
            return
        settings = db.get_settings()
        settings["materials"][name] = value
        db.set_setting("materials", settings["materials"])
        self.new_material_name.value = ""
        self.new_material_price.value = ""
        self.status_text.value = f"Добавлено: {name}"
        self.refresh()

    def _save_scalars(self, e: ft.ControlEvent) -> None:
        hour_rate = pricing.parse_number(self.hour_rate_field.value)
        reverse_price = pricing.parse_number(self.reverse_price_field.value)
        if hour_rate is not None:
            db.set_setting("hour_rate", hour_rate)
        if reverse_price is not None:
            db.set_setting("reverse_price", reverse_price)
        defect = pricing.parse_number(self.defect_field.value)
        if defect is not None:
            db.set_setting("defect_percent", defect)
        if self.currency_field.value:
            db.set_setting("currency", self.currency_field.value.strip())
        self.status_text.value = "Настройки сохранены."
        self.update()
