"""Список заказов и «Цены» с электроникой."""
import flet as ft

import db
from app.screens import orders_screen
from app.screens.prices_screen import PricesScreen


def test_order_parts_icons_and_subtitle(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0, "material": "PLA",
                        "has_electronics": 1})
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 1}, {"name": "Экран", "qty": 1, "unit_cost": 1},
                            {"name": "Лента", "qty": 1, "unit_cost": 1}])
    icons, subtitle = orders_screen.order_parts(db.get_order(oid), db.list_components(oid))
    assert icons == [ft.Icons.PRECISION_MANUFACTURING, ft.Icons.MEMORY]
    assert subtitle == "PLA · ESP32, Экран…"


def test_order_parts_print_only_keeps_old_subtitle(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0, "description": "Крепление",
                        "material": "PETG"})
    icons, subtitle = orders_screen.order_parts(db.get_order(oid), [])
    assert icons == [ft.Icons.PRECISION_MANUFACTURING] and subtitle == "Крепление · PETG"


def test_orders_screen_renders_with_components(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0, "has_print": 0, "has_electronics": 1})
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 1}])
    screen = orders_screen.OrdersScreen(on_open_order=lambda i: None)
    assert len(screen.list_view.controls) == 1


def test_prices_screen_saves_components_markup(temp_db, monkeypatch):
    screen = PricesScreen()
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.refresh()
    assert screen.components_markup_field.value == "20"
    screen.components_markup_field.value = "30"
    screen._save_scalars(None)
    assert db.get_settings()["components_markup"] == 30
