"""Окно «Смета в Excel»: выбор периода (месяц / квартал / свои даты) и сохранение файла."""
from datetime import date
from typing import Callable

import flet as ft

import pricing
from app import input_hints, report, theme

KINDS = [("month", "Месяц"), ("quarter", "Квартал"), ("custom", "Свой период")]


class ReportDialog:
    """Живёт всё время работы приложения; FilePicker добавляется в page.overlay один раз."""

    def __init__(self, page: ft.Page, on_saved: Callable[[str], None], on_error: Callable[[str], None]):
        self.page = page
        self.on_saved = on_saved
        self.on_error = on_error
        self.picker = ft.FilePicker(on_result=self._on_file_chosen)
        page.overlay.append(self.picker)
        self._period: tuple[date, date] | None = None

        today = date.today()
        years = list(range(today.year - 5, today.year + 2))
        self.kind = ft.SegmentedButton(
            segments=[ft.Segment(value=k, label=ft.Text(label)) for k, label in KINDS],
            selected={"month"}, show_selected_icon=False, on_change=self._on_kind,
        )
        self.month_dd = theme.dropdown("Месяц", width=190, value=str(today.month), on_change=self._update_preview,
                                       options=[ft.dropdown.Option(str(i + 1), name)
                                                for i, name in enumerate(report.MONTHS_NOM)])
        self.quarter_dd = theme.dropdown("Квартал", width=190, value=str((today.month - 1) // 3 + 1),
                                         on_change=self._update_preview,
                                         options=[ft.dropdown.Option(str(q), f"{q} квартал") for q in range(1, 5)])
        self.year_dd = theme.dropdown("Год", width=130, value=str(today.year), on_change=self._update_preview,
                                      options=[ft.dropdown.Option(str(y)) for y in years])
        self.start_field = input_hints.date_field("С", col={"xs": 6}, value=today.replace(day=1).strftime("%d.%m.%Y"),
                                                  on_change=self._update_preview, on_pick=self._update_preview)
        self.end_field = input_hints.date_field("По", col={"xs": 6}, value=today.strftime("%d.%m.%Y"),
                                                on_change=self._update_preview, on_pick=self._update_preview)
        self.month_row = ft.Row([self.month_dd, self.year_dd], spacing=12)
        self.quarter_row = ft.Row([self.quarter_dd], spacing=12, visible=False)
        self.custom_row = theme.grid([self.start_field, self.end_field], visible=False)
        self.year_holder = ft.Row([], spacing=12)
        self.preview = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.save_button = ft.FilledButton("Скачать Excel", icon=ft.Icons.FILE_DOWNLOAD_OUTLINED,
                                           on_click=self._on_save)

        self.dialog = ft.AlertDialog(
            title=ft.Text("Смета в Excel"),
            content=ft.Container(ft.Column([
                ft.Text("Заказы за период с ценами, предоплатами, себестоимостью и прибылью; "
                        "на втором листе — итоги.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                self.kind, self.month_row, self.quarter_row, self.custom_row,
                ft.Divider(height=8, color=ft.Colors.OUTLINE_VARIANT), self.preview,
            ], spacing=14, tight=True), width=460),
            actions=[ft.TextButton("Отмена", on_click=lambda e: page.close(self.dialog)), self.save_button],
        )

    # ---------- выбор периода ----------

    def open(self) -> None:
        self._update_preview(None)
        self.page.open(self.dialog)

    def _on_kind(self, e: ft.ControlEvent) -> None:
        kind = next(iter(self.kind.selected), "month")
        self.month_row.visible = kind == "month"
        self.quarter_row.visible = kind == "quarter"
        self.custom_row.visible = kind == "custom"
        # Год общий для месяца и квартала — переносим выпадающий список в видимую строку.
        for row in (self.month_row, self.quarter_row):
            if self.year_dd in row.controls:
                row.controls.remove(self.year_dd)
        if kind in ("month", "quarter"):
            (self.month_row if kind == "month" else self.quarter_row).controls.append(self.year_dd)
        self._update_preview(None)

    def period(self) -> tuple[date, date] | None:
        kind = next(iter(self.kind.selected), "month")
        year = int(self.year_dd.value)
        if kind == "month":
            return report.month_period(year, int(self.month_dd.value))
        if kind == "quarter":
            return report.quarter_period(year, int(self.quarter_dd.value))
        start = pricing.parse_date(self.start_field.value)
        end = pricing.parse_date(self.end_field.value)
        if not start or not end:
            return None
        start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
        return (start_d, end_d) if start_d <= end_d else None

    def _update_preview(self, e) -> None:
        self._period = self.period()
        if self._period is None:
            self.preview.value = "Укажите даты: «С» не позже «По», например 01.09.2026 – 30.09.2026."
            self.preview.color = theme.ERR
            self.save_button.disabled = True
        else:
            start, end = self._period
            rows = report.report_rows(start, end)
            total = report.summary(rows)
            self.preview.value = (f"{report.period_title(start, end)} · {len(rows)} заказ(ов) · "
                                  f"сумма {pricing.money(total['price'])} · прибыль {pricing.money(total['profit'])}")
            self.preview.color = ft.Colors.ON_SURFACE_VARIANT
            self.save_button.disabled = False
        if self.dialog.open and self.page:
            self.dialog.update()

    # ---------- сохранение ----------

    def _on_save(self, e: ft.ControlEvent) -> None:
        if self._period is None:
            return
        self.page.close(self.dialog)
        self.picker.save_file(dialog_title="Сохранить смету", file_name=report.default_file_name(*self._period),
                              allowed_extensions=["xlsx"])

    def _on_file_chosen(self, e: ft.FilePickerResultEvent) -> None:
        if not e.path or self._period is None:
            return
        try:
            saved = report.write_report(e.path, *self._period)
            self.on_saved(str(saved))
        except Exception as exc:  # noqa: BLE001 - ошибка записи (файл открыт в Excel и т.п.) должна дойти до пользователя
            self.on_error(str(exc))
