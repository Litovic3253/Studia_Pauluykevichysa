"""Строки компонентов электроники в заказе: название, кол-во, закупка за штуку, сумма строки.
Общие для «Нового заказа» и карточки заказа. Названия и последние цены подсказываются из прошлых заказов."""
from typing import Callable, Iterable, Mapping

import flet as ft

import db
import pricing
from app import theme

NAME_COL = {"xs": 12, "sm": 5}
QTY_COL = {"xs": 4, "sm": 2}
COST_COL = {"xs": 5, "sm": 3}
SUM_COL = {"xs": 3, "sm": 2}


class _Row:
    def __init__(self, editor: "ComponentsEditor", name: str, qty, unit_cost):
        self.editor = editor
        live = editor.on_input if editor.live else None
        commit = None if editor.live else editor.on_commit
        self.name = theme.field("Компонент", NAME_COL, value=name, dense=True, hint_text="напр. ESP32",
                                on_change=live, on_blur=self.on_name_blur)
        self.qty = theme.field("Кол-во", QTY_COL, value=pricing.fmt_number(qty), dense=True,
                               on_change=self._on_number_change, on_blur=commit)
        self.cost = theme.field("Закупка за шт", COST_COL, suffix_text="₽", dense=True,
                                value="" if unit_cost is None else pricing.fmt_number(unit_cost),
                                on_change=self._on_number_change, on_blur=commit)
        self.sum_text = ft.Text("", size=13, text_align=ft.TextAlign.RIGHT)
        self.control = ft.Row([
            theme.grid([self.name, self.qty, self.cost,
                        ft.Container(self.sum_text, col=SUM_COL, alignment=ft.alignment.center_right, height=40)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=theme.tip("Убрать компонент"),
                          on_click=lambda e: editor.remove(self)),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.refresh_sum()

    def values(self, strict: bool) -> dict | None:
        """{name, qty, unit_cost}; strict — с ошибками у полей и None, если число не распознано."""
        qty_text, cost_text = (self.qty.value or "").strip(), (self.cost.value or "").strip()
        qty = pricing.parse_number(qty_text) if qty_text else 1
        cost = pricing.parse_number(cost_text) if cost_text else 0
        if strict:
            self.qty.error_text = None if qty is not None else "Число"
            self.cost.error_text = None if cost is not None else "Сумма числом"
            if qty is None or cost is None:
                return None
        return {"name": (self.name.value or "").strip(), "qty": qty or 0, "unit_cost": cost or 0}

    def refresh_sum(self) -> None:
        v = self.values(strict=False)
        self.sum_text.value = pricing.money(v["qty"] * v["unit_cost"]) if v["name"] or v["unit_cost"] else ""

    def _on_number_change(self, e) -> None:
        self.refresh_sum()
        if self.editor.live:
            self.editor.on_input(e)
        else:
            self.editor.safe_update()

    def on_name_blur(self, e) -> None:
        """Знакомое название — написание и последняя цена из прошлых заказов (если цену ещё не вводили)."""
        typed = (self.name.value or "").strip()
        known = next((n for n in self.editor.catalog if n.lower() == typed.lower()), None)
        if known:
            self.name.value = known
            if pricing.parse_number(self.cost.value) in (None, 0):
                self.cost.value = pricing.fmt_number(self.editor.catalog[known])
        self.refresh_sum()
        if self.editor.live:
            self.editor.on_input(e)
        else:
            self.editor.on_commit(e)


class ComponentsEditor(ft.Column):
    def __init__(self, on_change: Callable[[], None] | None = None, live: bool = True):
        super().__init__(spacing=8)
        self.on_change = on_change
        self.live = live
        self.rows: list[_Row] = []
        self.catalog: dict[str, float] = {}
        self.rows_column = ft.Column(spacing=8)
        self.empty_text = ft.Text("Компонентов пока нет.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.catalog_menu = ft.PopupMenuButton(
            content=ft.Row([ft.Icon(ft.Icons.HISTORY, size=18), ft.Text("Из прошлых заказов", size=13)],
                           spacing=6, tight=True),
            tooltip=theme.tip("Компоненты, которые уже были в заказах, — с последней ценой"), items=[],
            visible=False,
        )
        self.controls = [
            self.rows_column,
            ft.Row([ft.OutlinedButton("Компонент", icon=ft.Icons.ADD, on_click=lambda e: self._add_clicked()),
                    self.catalog_menu], spacing=12, wrap=True),
        ]
        self._render()

    # ---------- данные ----------

    def load_catalog(self) -> None:
        self.catalog = db.component_catalog()
        self.catalog_menu.items = [
            ft.PopupMenuItem(text=f"{name} — {pricing.money(cost)}", on_click=lambda e, n=name: self.pick(n))
            for name, cost in self.catalog.items()
        ]
        self.catalog_menu.visible = bool(self.catalog)

    def set_components(self, rows: Iterable[Mapping]) -> None:
        self.load_catalog()
        self.rows = [_Row(self, r["name"], r["qty"], r["unit_cost"]) for r in rows]
        self._render()

    def add_row(self, name: str = "", qty: float = 1, unit_cost: float | None = None) -> None:
        self.rows.append(_Row(self, name, qty, unit_cost))
        self._render()

    def pick(self, name: str) -> None:
        """Выбор из прошлых заказов: в пустую последнюю строку или новой строкой."""
        cost = self.catalog.get(name, 0)
        last = self.rows[-1] if self.rows else None
        if last and not (last.name.value or "").strip():
            last.name.value, last.cost.value = name, pricing.fmt_number(cost)
            last.refresh_sum()
        else:
            self.add_row(name, 1, cost)
        self._changed()

    def remove(self, row: _Row) -> None:
        self.rows.remove(row)
        self._render()
        self._changed()

    def get_components(self) -> list[dict] | None:
        """Компоненты для сохранения; None — если в кол-ве или цене не число (ошибка у поля)."""
        values = [r.values(strict=True) for r in self.rows]
        if any(v is None for v in values):
            self.safe_update()
            return None
        return [v for v in values if v["name"]]

    def preview(self) -> list[dict]:
        """Для живого расчёта: нераспознанные числа считаются нулём."""
        return [v for v in (r.values(strict=False) for r in self.rows) if v["name"]]

    # ---------- события ----------

    def on_input(self, e) -> None:
        if self.on_change:
            self.on_change()

    def on_commit(self, e) -> None:
        if self.on_change:
            self.on_change()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()
        self.safe_update()

    def _add_clicked(self) -> None:
        self.add_row()
        self.safe_update()

    def _render(self) -> None:
        self.rows_column.controls = [r.control for r in self.rows] or [self.empty_text]

    def safe_update(self) -> None:
        try:
            self.update()
        except AssertionError:  # ещё не на странице
            pass
