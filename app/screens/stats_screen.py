"""Экран «Статистика»: плитки с ключевыми цифрами и полоски по статусам и материалам."""
import flet as ft

import db
import pricing
from app import theme


class StatsScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.header = ft.Container()
        self.kpi_grid = theme.grid([])
        self.status_column = ft.Column(spacing=10)
        self.material_column = ft.Column(spacing=10)
        self.controls = [
            self.header,
            self.kpi_grid,
            theme.grid([
                theme.section("Заказы по статусам", [self.status_column], icon=ft.Icons.DONUT_SMALL,
                              col={"xs": 12, "lg": 6}),
                theme.section("Расход материала", [self.material_column], icon=ft.Icons.INVENTORY_2_OUTLINED,
                              col={"xs": 12, "lg": 6}),
            ]),
        ]
        self.refresh()

    def refresh(self) -> None:
        s = db.stats()
        total = sum(s["by_status"].values())

        self.header.content = theme.page_header(
            "Статистика",
            f"В этом месяце: {s['month_orders']} заказов, оплачено {pricing.money(s['month_revenue'])}",
        )
        self.kpi_grid.controls = [
            self._kpi("Выручка", pricing.money(s["revenue"]), ft.Icons.PAYMENTS_OUTLINED, ft.Colors.GREEN),
            self._kpi("Прибыль", pricing.money(s["profit"]), ft.Icons.TRENDING_UP, ft.Colors.BLUE),
            self._kpi("Ждём оплату", pricing.money(s["unpaid"]), ft.Icons.HOURGLASS_BOTTOM, ft.Colors.ORANGE_800),
            self._kpi("Заказов всего", str(total), ft.Icons.RECEIPT_LONG, ft.Colors.DEEP_PURPLE),
        ]

        self.status_column.controls = [
            self._bar(*theme.status_style(code), s["by_status"][code], total, str(s["by_status"][code]))
            for code in db.STATUSES if s["by_status"].get(code)
        ] or [ft.Text("Заказов пока нет.", color=ft.Colors.ON_SURFACE_VARIANT)]

        grams_total = s["grams"] or 0
        self.material_column.controls = [
            self._bar(name, ft.Colors.PRIMARY, grams, grams_total, f"{grams / 1000:.2f} кг")
            for name, grams in s["materials"]
        ] or [ft.Text("Пока ничего не напечатано.", color=ft.Colors.ON_SURFACE_VARIANT)]
        if s["materials"]:
            self.material_column.controls.append(
                ft.Text(f"Всего {grams_total / 1000:.2f} кг", size=12, color=ft.Colors.ON_SURFACE_VARIANT))

        if self.page:
            self.update()

    def _kpi(self, label: str, value: str, icon, color) -> ft.Control:
        return theme.card(
            ft.Row([
                ft.Container(ft.Icon(icon, color=color), padding=10, border_radius=12,
                             bgcolor=ft.Colors.with_opacity(0.12, color)),
                ft.Column([
                    ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(value, size=20, weight=ft.FontWeight.W_700, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, tight=True, expand=True),
            ], spacing=12),
            col={"xs": 12, "sm": 6, "xl": 3},
        )

    def _bar(self, label: str, color, value: float, total: float, value_text: str) -> ft.Control:
        share = value / total if total else 0
        return ft.Column([
            ft.Row([ft.Text(label, expand=True),
                    ft.Text(value_text, weight=ft.FontWeight.W_600),
                    ft.Text(f"{share:.0%}", size=12, color=ft.Colors.ON_SURFACE_VARIANT, width=40,
                            text_align=ft.TextAlign.RIGHT)]),
            ft.ProgressBar(value=share, color=color, bgcolor=ft.Colors.with_opacity(0.12, color),
                           bar_height=8, border_radius=4),
        ], spacing=4)
