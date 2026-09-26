"""Поля «Вес» и «Часы печати» с выпадающим меню примеров и проверкой ввода."""
from typing import Callable

import flet as ft

import pricing
from app import theme

WEIGHT_EXAMPLES = ["454,28", "454.28", "454,28 г", "50"]
HOURS_EXAMPLES = ["2.5", "2ч 30м", "2ч 30 мин", "2:30", "150 мин", "1д 6ч 46м"]

WEIGHT_HELP = "Можно с дробью: 454,28"
HOURS_HELP = "2.5 · 2ч 30м · 1д 6ч 46м"


def _examples_menu(field: ft.TextField, examples: list[str], describe: Callable[[str], str],
                   on_pick: Callable[[], None] | None) -> ft.PopupMenuButton:
    def pick(example: str) -> None:
        field.value = example
        if on_pick:
            on_pick()
        if field.page:
            field.update()

    return ft.PopupMenuButton(
        icon=ft.Icons.HELP_OUTLINE,
        tooltip=theme.tip("Как заполнять — нажмите на пример, чтобы подставить"),
        items=[ft.PopupMenuItem(text=describe(ex), on_click=lambda e, ex=ex: pick(ex)) for ex in examples],
    )


def weight_field(on_pick: Callable[[], None] | None = None, **kwargs) -> ft.TextField:
    field = ft.TextField(label="Вес, г", helper_text=WEIGHT_HELP, border_radius=10, **kwargs)
    field.suffix_icon = _examples_menu(
        field, WEIGHT_EXAMPLES,
        lambda ex: f"{ex}  →  {pricing.fmt_number(pricing.parse_weight(ex))} г", on_pick,
    )
    return field


def hours_field(on_pick: Callable[[], None] | None = None, **kwargs) -> ft.TextField:
    field = ft.TextField(label="Часы печати", helper_text=HOURS_HELP, border_radius=10, **kwargs)
    field.suffix_icon = _examples_menu(
        field, HOURS_EXAMPLES,
        lambda ex: f"{ex}  →  {pricing.fmt_number(pricing.parse_hours(ex))} ч", on_pick,
    )
    return field


def check_weight(field: ft.TextField) -> float | None:
    """Разбирает вес; пустое поле = 0. При ошибке подсвечивает поле и возвращает None."""
    if not (field.value or "").strip():
        field.error_text = None
        return 0
    value = pricing.parse_weight(field.value)
    field.error_text = None if value is not None else "Не понял число. Пример: 454,28"
    return value


def check_hours(field: ft.TextField) -> float | None:
    """Разбирает часы и показывает под полем пересчёт в десятичные часы («= 2,5 ч»)."""
    if not (field.value or "").strip():
        field.error_text = None
        field.helper_text = HOURS_HELP
        return 0
    value = pricing.parse_hours(field.value)
    if value is None:
        field.error_text = "Не понял время. Пример: 2ч 30м или 1д 6ч 46м"
        return None
    field.error_text = None
    field.helper_text = f"= {pricing.fmt_number(value)} ч"
    return value


def date_field(label: str, on_pick: Callable[[], None] | None = None, col=None, **kwargs) -> ft.TextField:
    """Поле даты: точки ставятся сами по мере набора («27092026» → «27.09.2026»),
    справа — календарь; выбранная дата сразу вписывается в поле, затем вызывается on_pick."""
    from datetime import date, datetime

    user_on_change = kwargs.pop("on_change", None)
    field = theme.field(label, col, **kwargs)

    def on_change(e: ft.ControlEvent) -> None:
        formatted = pricing.format_date_input(field.value)
        if formatted != field.value:
            field.value = formatted
            if field.page:
                field.update()
        if user_on_change:
            user_on_change(e)

    def picked(e: ft.ControlEvent) -> None:
        if picker.value:
            field.value = picker.value.strftime("%d.%m.%Y")
            field.error_text = None
            if on_pick:
                on_pick()
            if field.page:
                field.update()

    picker = ft.DatePicker(
        first_date=datetime(2020, 1, 1), last_date=datetime(2040, 12, 31),
        date_picker_entry_mode=ft.DatePickerEntryMode.CALENDAR_ONLY,
        help_text="Выберите дату", cancel_text="Отмена", confirm_text="Готово",
        on_change=picked,
    )

    def open_calendar(e: ft.ControlEvent) -> None:
        iso = pricing.parse_date(field.value)
        picker.value = datetime.fromisoformat(iso) if iso else datetime.combine(date.today(), datetime.min.time())
        field.page.open(picker)

    field.on_change = on_change
    # suffix_icon, а не suffix: кнопка в suffix делает поле выше соседних.
    field.suffix_icon = ft.IconButton(ft.Icons.CALENDAR_MONTH_OUTLINED, icon_size=18, tooltip=theme.tip("Выбрать в календаре"),
                                 on_click=open_calendar)
    field.data = picker  # для тестов и повторного открытия
    return field
