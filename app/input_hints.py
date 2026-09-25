"""Поля «Вес» и «Часы печати» с выпадающим меню примеров и проверкой ввода."""
from typing import Callable

import flet as ft

import pricing

WEIGHT_EXAMPLES = ["454,28", "454.28", "454,28 г", "50"]
HOURS_EXAMPLES = ["2.5", "2ч 30м", "2ч 30 мин", "2:30", "150 мин", "1д 6ч 46м"]

WEIGHT_HELP = "Граммы, можно с дробью: 454,28 или 454.28"
HOURS_HELP = "Например: 2.5 · 2ч 30м · 1д 6ч 46м (1д = 24ч)"


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
        tooltip="Как заполнять — нажмите на пример, чтобы подставить",
        items=[ft.PopupMenuItem(text=describe(ex), on_click=lambda e, ex=ex: pick(ex)) for ex in examples],
    )


def weight_field(on_pick: Callable[[], None] | None = None, **kwargs) -> ft.TextField:
    field = ft.TextField(label="Вес, г", helper_text=WEIGHT_HELP, **kwargs)
    field.suffix = _examples_menu(
        field, WEIGHT_EXAMPLES,
        lambda ex: f"{ex}  →  {pricing.fmt_number(pricing.parse_weight(ex))} г", on_pick,
    )
    return field


def hours_field(on_pick: Callable[[], None] | None = None, **kwargs) -> ft.TextField:
    field = ft.TextField(label="Часы печати", helper_text=HOURS_HELP, **kwargs)
    field.suffix = _examples_menu(
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
