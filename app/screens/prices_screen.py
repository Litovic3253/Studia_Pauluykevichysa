"""Экран «Цены»: пластик (закупка → цена для клиента) и настройки расчёта (ставка часа, реверс, брак, валюта)."""
import flet as ft

import db
import pricing
from app import theme

NAME_COL = {"xs": 12, "sm": 3}
PURCHASE_COL = {"xs": 5, "sm": 4}
PRICE_COL = {"xs": 5, "sm": 4}
ACTION_COL = {"xs": 2, "sm": 1}


class PricesScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.materials_column = ft.Column(spacing=4)
        self.new_material_name = theme.field("Пластик", NAME_COL, hint_text="напр. TPU", dense=True)
        self.new_material_purchase = theme.field("Закупка", PURCHASE_COL, suffix_text="₽/г", dense=True,
                                                 hint_text="за что купил")
        self.new_material_price = theme.field("Цена клиенту", PRICE_COL, suffix_text="₽/г", dense=True)
        self.hour_rate_field = theme.field("Ставка часа печати", {"xs": 12, "sm": 6}, suffix_text="₽/ч",
                                           helper_text="Входит в цену заказа", on_blur=self._save_scalars)
        self.reverse_price_field = theme.field("Реверс-моделирование", {"xs": 12, "sm": 6}, suffix_text="₽",
                                               helper_text="Если у клиента нет 3D-модели", on_blur=self._save_scalars)
        self.defect_field = theme.field(
            "Процент брака по умолчанию", {"xs": 12, "sm": 6}, suffix_text="%", on_blur=self._save_scalars,
            helper_text="Подставляется в новые заказы",
        )
        self.currency_field = theme.field("Валюта", {"xs": 12, "sm": 6}, on_blur=self._save_scalars)
        self.prepayment_percent_field = theme.field(
            "Предоплата в PDF", {"xs": 12, "sm": 6}, suffix_text="%", on_blur=self._save_scalars,
            helper_text="Сколько клиенту внести сразу; 0 — не писать",
        )
        self.payment_field = theme.field(
            "Оплата в PDF для клиента", {"xs": 12}, on_blur=self._save_scalars,
            multiline=True, min_lines=3, hint_text="+79001234567\nИмя Отчество\nБанк",
            helper_text="Печатается внизу PDF под «Оплата:» — строка в строку. Пусто — блока не будет",
        )
        self.status_text = ft.Text("", size=13, color=theme.OK)
        self.status_row = ft.Container(self.status_text, visible=False)

        def head(text: str, col) -> ft.Control:
            return ft.Text(text, size=12, color=ft.Colors.ON_SURFACE_VARIANT, col=col)

        materials = theme.section("Пластик: закупка и цена", [
            ft.Text("Закупка — сколько пластик стоил вам, из неё считается себестоимость и прибыль. "
                    "Цена клиенту — по ней считается цена заказа.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            theme.grid([head("Пластик", NAME_COL), head("Закупка, за грамм", PURCHASE_COL),
                        head("Цена клиенту, за грамм", PRICE_COL)], run_spacing=0),
            self.materials_column,
            ft.Divider(height=8),
            theme.grid([
                self.new_material_name, self.new_material_purchase, self.new_material_price,
                ft.Container(ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.PRIMARY, icon_size=30,
                                           tooltip=theme.tip("Добавить пластик"), on_click=self._add_material),
                             col=ACTION_COL, alignment=ft.alignment.center_left),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], icon=ft.Icons.INVENTORY_2_OUTLINED, col={"xs": 12, "lg": 7})

        settings = theme.section("Расчёт цены", [
            theme.grid([self.hour_rate_field, self.reverse_price_field, self.defect_field, self.currency_field,
                        self.prepayment_percent_field, self.payment_field]),
            ft.Text("Изменения сохраняются, когда вы уходите из поля. Цены уже созданных заказов не меняются, "
                    "а их себестоимость и прибыль пересчитываются по новой закупке.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Divider(height=8),
            ft.Text("Как считается прибыль", size=13, weight=ft.FontWeight.W_600),
            ft.Text("Прибыль = цена заказа − пластик по закупке. "
                    "Часы печати, наценка на пластик, брак, реверс-моделирование и ручная цена — всё это прибыль.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ], icon=ft.Icons.TUNE, col={"xs": 12, "lg": 5})

        self.controls = [
            theme.page_header("Цены", "Закупка пластика, цены для клиента и параметры расчёта"),
            self.status_row,
            theme.grid([materials, settings]),
        ]
        self.refresh()

    def update(self) -> None:
        self.status_row.visible = bool(self.status_text.value)
        super().update()

    def refresh(self) -> None:
        settings = db.get_settings()
        purchase = settings["purchase_prices"]
        self.materials_column.controls = [
            self._material_row(name, purchase.get(name), price) for name, price in settings["materials"].items()
        ] or [ft.Text("Пластика нет — добавьте первый ниже.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)]
        self.hour_rate_field.value = pricing.fmt_number(settings["hour_rate"])
        self.reverse_price_field.value = pricing.fmt_number(settings["reverse_price"])
        self.defect_field.value = pricing.fmt_number(settings["defect_percent"])
        self.currency_field.value = settings["currency"]
        self.payment_field.value = settings["payment_text"]
        self.prepayment_percent_field.value = pricing.fmt_number(settings["prepayment_percent"])
        if self.page:
            self.update()

    def _say(self, text: str, ok: bool = True) -> None:
        self.status_text.color = theme.OK if ok else theme.ERR
        self.status_text.value = text

    def _material_row(self, name: str, purchase: float | None, price: float) -> ft.Control:
        def number_field(value, col, hint: str = "") -> ft.TextField:
            return ft.TextField(value=pricing.fmt_number(value) if value else "", dense=True, suffix_text="₽/г",
                                hint_text=hint, border_radius=theme.FIELD_RADIUS, text_align=ft.TextAlign.RIGHT,
                                col=col, **theme.FIELD_BORDER)

        purchase_field = number_field(purchase, PURCHASE_COL, "не указана")
        price_field = number_field(price, PRICE_COL)
        margin_text = ft.Text(self._margin_label(purchase, price), size=11, color=ft.Colors.ON_SURFACE_VARIANT)

        def save(field: ft.TextField, key: str) -> None:
            text = (field.value or "").strip()
            value = pricing.parse_number(text)
            if value is None and not (key == "purchase_prices" and not text):
                field.error_text = "Число"
                self.update()
                return
            field.error_text = None
            settings = db.get_settings()
            if value is None:
                settings[key].pop(name, None)  # закупку стёрли — «не указана»
            else:
                settings[key][name] = value
            db.set_setting(key, settings[key])
            if key == "purchase_prices":
                db.recalc_costs()
                self._say(f"Сохранено: закупка {name} — {pricing.fmt_number(value)} ₽/г" if value is not None
                          else f"Закупка {name} не указана")
            else:
                self._say(f"Сохранено: {name} для клиента — {pricing.fmt_number(value)} ₽/г")
            settings = db.get_settings()
            margin_text.value = self._margin_label(settings["purchase_prices"].get(name), settings["materials"][name])
            self.update()

        def delete(e: ft.ControlEvent) -> None:
            settings = db.get_settings()
            settings["materials"].pop(name, None)
            settings["purchase_prices"].pop(name, None)
            db.set_setting("materials", settings["materials"])
            db.set_setting("purchase_prices", settings["purchase_prices"])
            self._say(f"Удалено: {name}")
            self.refresh()

        purchase_field.on_blur = lambda e: save(purchase_field, "purchase_prices")
        price_field.on_blur = lambda e: save(price_field, "materials")
        row = theme.grid([
            ft.Column([ft.Text(name, weight=ft.FontWeight.W_600), margin_text], spacing=0, tight=True, col=NAME_COL),
            purchase_field, price_field,
            ft.Container(ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=theme.tip(f"Удалить {name}"), on_click=delete),
                         col=ACTION_COL, alignment=ft.alignment.center_left),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, run_spacing=6)
        return theme.add_hover(ft.Container(row, padding=ft.padding.symmetric(horizontal=8, vertical=6),
                                            border_radius=12, border=ft.border.all(1, ft.Colors.TRANSPARENT)))

    @staticmethod
    def _margin_label(purchase: float | None, price: float) -> str:
        if not purchase:
            return "укажите закупку"
        return f"наценка +{pricing.fmt_number(price - purchase)} {db.get_settings()['currency']}/г"

    def _add_material(self, e: ft.ControlEvent) -> None:
        name = (self.new_material_name.value or "").strip()
        value = pricing.parse_number(self.new_material_price.value)
        purchase_text = (self.new_material_purchase.value or "").strip()
        purchase = pricing.parse_number(purchase_text)
        if not name or value is None or (purchase_text and purchase is None):
            self._say("Укажите название пластика и цену для клиента (закупка — числом, можно позже).", ok=False)
            self.update()
            return
        settings = db.get_settings()
        settings["materials"][name] = value
        db.set_setting("materials", settings["materials"])
        if purchase is not None:
            settings["purchase_prices"][name] = purchase
            db.set_setting("purchase_prices", settings["purchase_prices"])
            db.recalc_costs()
        self.new_material_name.value = ""
        self.new_material_purchase.value = ""
        self.new_material_price.value = ""
        self._say(f"Добавлено: {name}")
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
        db.set_setting("payment_text", (self.payment_field.value or "").strip())
        percent = pricing.parse_number(self.prepayment_percent_field.value)
        if percent is not None and percent <= 100:
            db.set_setting("prepayment_percent", percent)
        self._say("Настройки сохранены.")
        self.update()
