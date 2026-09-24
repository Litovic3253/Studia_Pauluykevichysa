"""Экран «Статистика»: выручка, прибыль, долги, расход материала."""
import flet as ft

import db
import pricing


class StatsScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=10)
        self.content_column = ft.Column(spacing=6)
        self.controls = [ft.Text("Статистика", size=20, weight=ft.FontWeight.BOLD), self.content_column]
        self.refresh()

    def refresh(self) -> None:
        s = db.stats()
        total = sum(s["by_status"].values())
        status_lines = [
            ft.Text(f"{label}: {s['by_status'].get(code, 0)}")
            for code, label in db.STATUSES.items() if s["by_status"].get(code)
        ] or [ft.Text("Заказов пока нет.", italic=True)]
        material_lines = [
            ft.Text(f"• {name}: {grams / 1000:.2f} кг") for name, grams in s["materials"]
        ] or [ft.Text("—")]

        self.content_column.controls = [
            ft.Text(f"Всего заказов: {total}"),
            *status_lines,
            ft.Divider(),
            ft.Text(f"Этот месяц: {s['month_orders']} заказов, оплачено {pricing.money(s['month_revenue'])}"),
            ft.Divider(),
            ft.Text(f"💰 Выручка (оплачено): {pricing.money(s['revenue'])}", weight=ft.FontWeight.BOLD),
            ft.Text(f"📈 Прибыль: {pricing.money(s['profit'])}", weight=ft.FontWeight.BOLD),
            ft.Text(f"💸 Ждём оплату: {pricing.money(s['unpaid'])}", weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text(f"Расход материала (всего {s['grams'] / 1000:.2f} кг):", weight=ft.FontWeight.BOLD),
            *material_lines,
        ]
        if self.page:
            self.update()
