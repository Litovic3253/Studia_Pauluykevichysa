"""Разбивка цены заказа строками — общая для «Нового заказа» и карточки заказа."""
import flet as ft

import pricing
from app import theme


def breakdown_rows(calc: dict, defect_percent: float, total: float | None = None) -> list[ft.Control]:
    """Печать (материал / время / брак / реверс) и электроника (компоненты / пайка / прошивка) — только
    включённые части, затем «Итого». total — если цена задана вручную."""
    rows = []
    if calc.get("has_print", True):
        rows += [theme.kv_row("Материал", pricing.money(calc["material_cost"])),
                 theme.kv_row("Время печати", pricing.money(calc["time_cost"]))]
        if defect_percent:
            rows.append(theme.kv_row(f"Брак {pricing.fmt_number(defect_percent)}%",
                                     f"+{pricing.money(calc['defect_cost'])}"))
        if calc["reverse_cost"]:
            rows.append(theme.kv_row("Реверс-моделирование", pricing.money(calc["reverse_cost"])))
    if calc.get("has_electronics"):
        rows.append(theme.kv_row("Компоненты", pricing.money(calc["components_cost"])))
        if calc["soldering_cost"]:
            rows.append(theme.kv_row("Пайка и сборка", pricing.money(calc["soldering_cost"])))
        if calc["firmware_cost"]:
            rows.append(theme.kv_row("Программирование", pricing.money(calc["firmware_cost"])))
    rows.append(ft.Divider(height=8))
    rows.append(theme.kv_row("Итого", pricing.money(calc["price"] if total is None else total), bold=True))
    return rows


def profit_rows(calc: dict, material: str | None, total: float | None = None) -> list[ft.Control]:
    """Себестоимость (пластик и компоненты по закупке) и прибыль — всё, что сверх неё.
    total — фактическая цена заказа, если задана вручную."""
    price = calc["price"] if total is None else total
    profit = price - calc["cost"]
    rows = []
    if calc.get("has_print", True):
        rows.append(theme.kv_row("Пластик по закупке", f"−{pricing.money(calc['purchase_cost'])}"))
    if calc.get("has_electronics"):
        rows.append(theme.kv_row("Компоненты по закупке", f"−{pricing.money(calc['components_purchase'])}"))
    rows.append(theme.kv_row("Прибыль", pricing.money(profit), bold=True,
                             color=theme.OK if profit >= 0 else theme.ERR))
    if calc.get("has_print", True) and material and not calc["has_purchase_price"]:
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
