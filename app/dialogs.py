"""Общие диалоги."""
import flet as ft

import pricing
from app import theme


def grams_dialog(page: ft.Page, title: str, label: str, value: str, on_ok, helper: str | None = None,
                 allow_zero: bool = False, extra: list[ft.Control] | None = None) -> None:
    """Диалог ввода количества граммов с проверкой."""
    field = ft.TextField(label=label, value=value, suffix_text="г", autofocus=True, helper_text=helper,
                         border_radius=theme.FIELD_RADIUS, **theme.FIELD_BORDER)

    def submit(e: ft.ControlEvent) -> None:
        amount = pricing.parse_weight(field.value)
        if amount is None or (amount <= 0 and not allow_zero):
            field.error_text = "Введите число граммов, например 250"
            field.update()
            return
        page.close(dialog)
        on_ok(amount)

    field.on_submit = submit
    dialog = ft.AlertDialog(
        title=ft.Text(title),
        content=ft.Column([*(extra or []), field], tight=True, width=380),
        actions=[ft.TextButton("Отмена", on_click=lambda e: page.close(dialog)),
                 ft.FilledButton("Готово", on_click=submit)],
    )
    page.open(dialog)
