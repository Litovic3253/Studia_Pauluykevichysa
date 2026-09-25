"""Экран «Цены»: таблица материалов и настройки расчёта (ставка часа, реверс, брак, валюта)."""
import flet as ft

import db
import pricing
from app import theme


class PricesScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.materials_column = ft.Column(spacing=8)
        self.new_material_name = theme.field("Новый материал", {"xs": 12, "sm": 5}, hint_text="напр. TPU", dense=True)
        self.new_material_price = theme.field("Цена", {"xs": 8, "sm": 4}, suffix_text="₽/кг", dense=True)
        self.hour_rate_field = theme.field("Ставка часа печати", {"xs": 12, "sm": 6}, suffix_text="₽/ч", on_blur=self._save_scalars)
        self.reverse_price_field = theme.field("Реверс-моделирование", {"xs": 12, "sm": 6}, suffix_text="₽",
                                               helper_text="Если у клиента нет 3D-модели", on_blur=self._save_scalars)
        self.defect_field = theme.field(
            "Процент брака по умолчанию", {"xs": 12, "sm": 6}, suffix_text="%", on_blur=self._save_scalars,
            helper_text="Подставляется в новые заказы",
        )
        self.currency_field = theme.field("Валюта", {"xs": 12, "sm": 6}, on_blur=self._save_scalars)
        self.status_text = ft.Text("", size=13, color=ft.Colors.GREEN)
        self.status_row = ft.Container(self.status_text, visible=False)

        materials = theme.section("Материалы", [
            ft.Row([ft.Text("Название", size=12, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
                    ft.Text("Цена за кг", size=12, color=ft.Colors.ON_SURFACE_VARIANT, width=150),
                    ft.Container(width=40)]),
            self.materials_column,
            ft.Divider(height=8),
            theme.grid([
                self.new_material_name, self.new_material_price,
                ft.Container(ft.FilledTonalButton("Добавить", icon=ft.Icons.ADD, on_click=self._add_material),
                             col={"xs": 4, "sm": 3}, alignment=ft.alignment.center_left, padding=ft.padding.only(top=4)),
            ]),
        ], icon=ft.Icons.INVENTORY_2_OUTLINED, col={"xs": 12, "lg": 6})

        settings = theme.section("Расчёт цены", [
            theme.grid([self.hour_rate_field, self.reverse_price_field, self.defect_field, self.currency_field]),
            ft.Text("Изменения сохраняются, когда вы уходите из поля. Уже созданные заказы не пересчитываются.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ], icon=ft.Icons.TUNE, col={"xs": 12, "lg": 6})

        self.controls = [
            theme.page_header("Цены", "Материалы и параметры, по которым считается цена заказа"),
            self.status_row,
            theme.grid([materials, settings]),
        ]
        self.refresh()

    def update(self) -> None:
        self.status_row.visible = bool(self.status_text.value)
        super().update()

    def refresh(self) -> None:
        settings = db.get_settings()
        self.materials_column.controls = [
            self._material_row(name, price) for name, price in settings["materials"].items()
        ] or [ft.Text("Материалов нет — добавьте первый ниже.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)]
        self.hour_rate_field.value = pricing.fmt_number(settings["hour_rate"])
        self.reverse_price_field.value = pricing.fmt_number(settings["reverse_price"])
        self.defect_field.value = pricing.fmt_number(settings["defect_percent"])
        self.currency_field.value = settings["currency"]
        if self.page:
            self.update()

    def _material_row(self, name: str, price: float) -> ft.Control:
        price_field = ft.TextField(value=pricing.fmt_number(price), width=150, dense=True, suffix_text="₽/кг",
                                   border_radius=theme.FIELD_RADIUS, text_align=ft.TextAlign.RIGHT)

        def save(e: ft.ControlEvent) -> None:
            value = pricing.parse_number(price_field.value)
            if value is None:
                price_field.error_text = "Число"
                self.update()
                return
            price_field.error_text = None
            settings = db.get_settings()
            settings["materials"][name] = value
            db.set_setting("materials", settings["materials"])
            self.status_text.value = f"Сохранено: {name} — {pricing.fmt_number(value)} ₽/кг"
            self.update()

        def delete(e: ft.ControlEvent) -> None:
            settings = db.get_settings()
            settings["materials"].pop(name, None)
            db.set_setting("materials", settings["materials"])
            self.status_text.value = f"Удалено: {name}"
            self.refresh()

        price_field.on_blur = save
        return ft.Row([
            ft.Text(name, weight=ft.FontWeight.W_600, expand=True),
            price_field,
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=f"Удалить {name}", on_click=delete, width=40),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _add_material(self, e: ft.ControlEvent) -> None:
        name = (self.new_material_name.value or "").strip()
        value = pricing.parse_number(self.new_material_price.value)
        if not name or value is None:
            self.status_text.color = ft.Colors.RED
            self.status_text.value = "Укажите название материала и цену."
            self.update()
            return
        settings = db.get_settings()
        settings["materials"][name] = value
        db.set_setting("materials", settings["materials"])
        self.new_material_name.value = ""
        self.new_material_price.value = ""
        self.status_text.color = ft.Colors.GREEN
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
        self.status_text.color = ft.Colors.GREEN
        self.status_text.value = "Настройки сохранены."
        self.update()
