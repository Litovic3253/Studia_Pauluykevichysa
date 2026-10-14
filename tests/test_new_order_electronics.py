"""«Новый заказ» с электроникой (без запуска окна)."""
import db
from app.screens.new_order import NewOrderScreen


def _screen(monkeypatch):
    db.set_setting("materials", {"PLA": 4})
    db.set_setting("purchase_prices", {"PLA": 2})
    db.set_setting("hour_rate", 50)
    db.set_setting("defect_percent", 0)
    created = []
    screen = NewOrderScreen(on_created=created.append)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.components_editor.update = lambda: None
    screen.client_field.value = "Иван"
    return screen, created


def test_print_and_electronics_order(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.material_dd.value = "PLA"
    screen.weight_field.value = "100"
    screen.hours_field.value = "2"
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    screen.components_editor.add_row("ESP32", 2, 450)
    screen.markup_field.value = "20"
    screen.soldering_field.value = "500"
    screen.firmware_field.value = "1500"
    screen._on_save(None)
    o = db.get_order(created[0])
    assert (o["has_print"], o["has_electronics"]) == (1, 1)
    assert o["price"] == 500 + 1080 + 500 + 1500
    assert o["cost"] == 200 + 900
    assert [r["name"] for r in db.list_components(o["id"])] == ["ESP32"]


def test_electronics_only_ignores_print_fields(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.weight_field.value = "100"
    screen.print_switch.value = False
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    assert not screen.print_body.visible and screen.electronics_body.visible
    screen.components_editor.add_row("Лента", 1, 300)
    screen.markup_field.value = "0"
    screen._on_save(None)
    o = db.get_order(created[0])
    assert o["has_print"] == 0 and o["weight_g"] == 0 and o["material"] is None and o["price"] == 300


def test_no_parts_is_an_error(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.print_switch.value = False
    screen._on_parts_change(None)
    screen._on_save(None)
    assert not created and "электрон" in screen.error_text.value.lower()


def test_bad_component_price_blocks_save(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    screen.components_editor.add_row("ESP32", 1, 450)
    screen.components_editor.rows[0].cost.value = "пятьсот"
    screen._on_save(None)
    assert not created and screen.error_text.value


def test_markup_default_from_settings_and_reset(temp_db, monkeypatch):
    db.set_setting("components_markup", 35)
    screen, created = _screen(monkeypatch)
    assert screen.markup_field.value == "35"
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    screen.components_editor.add_row("ESP32", 1, 450)
    screen._on_save(None)
    assert created
    assert not screen.electronics_switch.value and screen.components_editor.rows == []
