"""Строки компонентов электроники: ввод, проверка чисел, подсказки из прошлых заказов."""
import db
from app.components_editor import ComponentsEditor


def _editor(**kw):
    ed = ComponentsEditor(**kw)
    ed.update = lambda: None
    return ed


def test_get_components_parses_rows_and_skips_blank(temp_db):
    ed = _editor()
    ed.add_row("ESP32", 2, 450)
    ed.add_row()  # пустая строка — не компонент
    assert ed.get_components() == [{"name": "ESP32", "qty": 2, "unit_cost": 450}]


def test_invalid_numbers_mark_field_and_return_none(temp_db):
    ed = _editor()
    ed.add_row("ESP32", 1, 450)
    ed.rows[0].cost.value = "пятьсот"
    assert ed.get_components() is None
    assert ed.rows[0].cost.error_text
    assert ed.preview() == [{"name": "ESP32", "qty": 1, "unit_cost": 0}]


def test_blank_qty_means_one_and_blank_price_zero(temp_db):
    ed = _editor()
    ed.add_row("Провод")
    ed.rows[0].qty.value = ""
    assert ed.get_components() == [{"name": "Провод", "qty": 1, "unit_cost": 0}]


def test_known_name_fills_last_price(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    changes = []
    ed = _editor(on_change=lambda: changes.append(1), live=False)
    ed.set_components([])
    ed.add_row()
    ed.rows[0].name.value = "esp32"
    ed.rows[0].on_name_blur(None)
    assert ed.rows[0].name.value == "ESP32" and ed.rows[0].cost.value == "450"
    assert changes


def test_pick_from_catalog_and_delete(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.set_components(oid, [{"name": "Экран", "qty": 1, "unit_cost": 700}])
    ed = _editor()
    ed.set_components([])
    ed.pick("Экран")
    assert ed.get_components() == [{"name": "Экран", "qty": 1, "unit_cost": 700}]
    ed.remove(ed.rows[0])
    assert ed.rows == []
