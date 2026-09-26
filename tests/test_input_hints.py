"""Тесты для app/input_hints.py — поля веса/часов с меню примеров и проверкой ввода."""
import flet as ft

from app import input_hints


def test_weight_field_has_examples_menu_that_fills_the_field():
    picked = []
    field = input_hints.weight_field(on_pick=lambda: picked.append(True))
    menu = field.suffix_icon
    assert isinstance(menu, ft.PopupMenuButton)
    texts = [item.text for item in menu.items]
    assert any("454,28" in t for t in texts)

    menu.items[0].on_click(None)

    assert field.value == input_hints.WEIGHT_EXAMPLES[0]
    assert picked == [True]


def test_hours_menu_shows_how_each_example_converts():
    field = input_hints.hours_field()
    texts = [item.text for item in field.suffix_icon.items]
    assert "2ч 30м  →  2,5 ч" in texts
    assert "1д 6ч 46м  →  30,77 ч" in texts


def test_check_weight_flags_bad_input_and_clears_on_good():
    field = input_hints.weight_field()
    field.value = "много"
    assert input_hints.check_weight(field) is None
    assert field.error_text

    field.value = "454,28 г"
    assert input_hints.check_weight(field) == 454.28
    assert not field.error_text


def test_check_weight_treats_empty_as_zero():
    field = input_hints.weight_field()
    field.value = ""
    assert input_hints.check_weight(field) == 0
    assert not field.error_text


def test_check_hours_shows_decimal_conversion():
    field = input_hints.hours_field()
    field.value = "2ч 30 мин"
    assert input_hints.check_hours(field) == 2.5
    assert not field.error_text
    assert field.helper_text == "= 2,5 ч"


def test_check_hours_flags_bad_input():
    field = input_hints.hours_field()
    field.value = "долго"
    assert input_hints.check_hours(field) is None
    assert field.error_text
