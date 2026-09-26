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


def profit_rows(calc: dict, material: str | None, total: float | None = None) -> list[ft.Control]:
    """Себестоимость (пластик по закупке + часы печати) и прибыль — всё, что сверх неё.
    total — фактическая цена заказа, если задана вручную."""
    price = calc["price"] if total is None else total
    profit = price - calc["cost"]
    rows = [
        theme.kv_row("Пластик по закупке", f"−{pricing.money(calc['purchase_cost'])}"),
        theme.kv_row("Часы печати", f"−{pricing.money(calc['time_cost'])}"),
        theme.kv_row("Прибыль", pricing.money(profit), bold=True,
                     color=theme.OK if profit >= 0 else theme.ERR),
    ]
    if material and not calc["has_purchase_price"]:
        rows.append(ft.Text(f"Закупка «{material}» не указана в «Ценах» — пластик считается бесплатным.",
                            size=12, color=theme.WARN))
    return rows


def profit_box(rows: list[ft.Control]) -> ft.Container:
    """Блок прибыли — отдельной подложкой под разбивкой цены."""
    return ft.Container(
        ft.Column(rows, spacing=6),
        padding=12, border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.07, theme.OK),
        border=ft.border.all(1, ft.Colors.with_opacity(0.25, theme.OK)),
    )
