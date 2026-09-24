"""Экран «Статистика»: карточки с ключевыми показателями и разбивка по статусам/материалам."""
import flet as ft

import db
import pricing
from app import theme


class StatsScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.kpi_row = ft.Row(spacing=theme.SPACING, wrap=True)
        self.details_column = ft.Column(spacing=6)
        self.controls = [
            ft.Text("Статистика", size=20, weight=ft.FontWeight.BOLD),
            self.kpi_row,
            theme.card(self.details_column),
        ]
        self.refresh()

    def refresh(self) -> None:
        s = db.stats()
        total = sum(s["by_status"].values())

        self.kpi_row.controls = [
            self._kpi_card("Выручка", pricing.money(s["revenue"])),
            self._kpi_card("Прибыль", pricing.money(s["profit"])),
            self._kpi_card("Ждём оплату", pricing.money(s["unpaid"])),
            self._kpi_card("Заказов всего", str(total)),
        ]

        status_lines = [
            ft.Text(f"{label}: {s['by_status'].get(code, 0)}")
            for code, label in db.STATUSES.items() if s["by_status"].get(code)
        ] or [ft.Text("Заказов пока нет.", italic=True)]
        material_lines = [
            ft.Text(f"• {name}: {grams / 1000:.2f} кг") for name, grams in s["materials"]
        ] or [ft.Text("—")]

        self.details_column.controls = [
            ft.Text(f"Этот месяц: {s['month_orders']} заказов, оплачено {pricing.money(s['month_revenue'])}"),
            ft.Divider(),
            ft.Text("По статусам:", weight=ft.FontWeight.BOLD),
            *status_lines,
            ft.Divider(),
            ft.Text(f"Расход материала (всего {s['grams'] / 1000:.2f} кг):", weight=ft.FontWeight.BOLD),
            *material_lines,
        ]

        if self.page:
            self.update()

    def _kpi_card(self, label: str, value: str) -> ft.Control:
        return theme.card(
            ft.Column([
                ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(value, size=20, weight=ft.FontWeight.BOLD),
            ], spacing=4, tight=True),
            width=180,
        )
