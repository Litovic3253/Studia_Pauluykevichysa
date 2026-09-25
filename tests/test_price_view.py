"""Тесты для app/price_view.py — разбивка цены строками «материал / время / брак / итого»."""
import flet as ft

import db
from app import price_view


def _texts(rows):
    return [c.value for r in rows for c in getattr(r, "controls", []) if isinstance(c, ft.Text)]


def test_breakdown_lists_each_component_and_total(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)
    db.set_setting("currency", "₽")
    calc = {"material_cost": 400, "time_cost": 100, "defect_cost": 50, "reverse_cost": 0, "cost": 550, "price": 550}

    texts = _texts(price_view.breakdown_rows(calc, defect_percent=10))

    assert "Материал" in texts and "400 ₽" in texts
    assert "Время печати" in texts and "100 ₽" in texts
    assert "Брак 10%" in texts and "+50 ₽" in texts
    assert "Итого" in texts and "550 ₽" in texts
    assert "Реверс-моделирование" not in texts


def test_breakdown_hides_zero_defect_and_shows_reverse(temp_db):
    db.set_setting("currency", "₽")
    calc = {"material_cost": 0, "time_cost": 0, "defect_cost": 0, "reverse_cost": 1000, "cost": 0, "price": 1000}

    texts = _texts(price_view.breakdown_rows(calc, defect_percent=0))

    assert not any(t.startswith("Брак") for t in texts)
    assert "Реверс-моделирование" in texts
