"""Разбивка цены заказа строками — общая для «Нового заказа» и карточки заказа."""
import flet as ft

import pricing
from app import theme


def breakdown_rows(calc: dict, defect_percent: float, total: float | None = None) -> list[ft.Control]:
    """Материал / Время / Брак / Реверс / Итого. total — если цена задана вручную."""
    rows = [
        theme.kv_row("Материал", pricing.money(calc["material_cost"])),
        theme.kv_row("Время печати", pricing.money(calc["time_cost"])),
    ]
    if defect_percent:
        rows.append(theme.kv_row(f"Брак {pricing.fmt_number(defect_percent)}%", f"+{pricing.money(calc['defect_cost'])}"))
    if calc["reverse_cost"]:
        rows.append(theme.kv_row("Реверс-моделирование", pricing.money(calc["reverse_cost"])))
    rows.append(ft.Divider(height=8))
    rows.append(theme.kv_row("Итого", pricing.money(calc["price"] if total is None else total), bold=True))
    return rows
