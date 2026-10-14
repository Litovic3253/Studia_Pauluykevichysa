"""Карточка заказа с электроникой (без запуска окна)."""
import db
from app.screens.order_detail import OrderDetailScreen


def _screen(monkeypatch, **extra):
    db.set_setting("materials", {"PLA": 4})
    db.set_setting("purchase_prices", {"PLA": 2})
    db.set_setting("hour_rate", 50)
    oid = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 100, "print_hours": 2,
                        "qty": 1, "cost": 200, "price": 500, **extra})
    screen = OrderDetailScreen(oid, on_back=lambda: None)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.components_editor.update = lambda: None
    screen.refresh()
    return screen, oid


def test_enable_electronics_and_save_components(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch)
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    assert db.get_order(oid)["has_electronics"] == 1
    screen.components_editor.add_row("ESP32", 2, 450)
    screen.markup_field.value = "0"
    screen.soldering_field.value = "500"
    screen._on_electronics_commit()
    o = db.get_order(oid)
    assert o["price"] == 500 + 900 + 500 and o["cost"] == 200 + 900 and o["soldering_price"] == 500
    assert [r["name"] for r in db.list_components(oid)] == ["ESP32"]


def test_bad_number_does_not_save(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch, has_electronics=1)
    screen.components_editor.add_row("ESP32", 1, 450)
    screen.components_editor.rows[0].qty.value = "два"
    screen._on_electronics_commit()
    assert db.list_components(oid) == []
    screen.soldering_field.value = "много"
    screen.components_editor.rows[0].qty.value = "1"
    screen._on_electronics_commit()
    assert screen.soldering_field.error_text and db.list_components(oid) == []


def test_disable_print_hides_usage_and_drops_print_price(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch, has_electronics=1, soldering_price=700)
    screen.print_switch.value = False
    screen._on_parts_change(None)
    o = db.get_order(oid)
    assert o["has_print"] == 0 and o["price"] == 700 and o["weight_g"] == 100  # поля печати сохранены
    assert not screen.print_body.visible and not screen.usage_row.visible


def test_cannot_disable_both_parts(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch)
    screen.print_switch.value = False
    screen._on_parts_change(None)
    assert db.get_order(oid)["has_print"] == 1 and screen.print_switch.value is True


def test_refresh_loads_components(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch, has_electronics=1)
    db.set_components(oid, [{"name": "Экран", "qty": 1, "unit_cost": 700}])
    screen.refresh()
    assert [r.name.value for r in screen.components_editor.rows] == ["Экран"]


def test_commit_keeps_row_controls_so_focus_stays(temp_db, monkeypatch):
    """После сохранения строки не пересоздаются: курсор остаётся в поле, куда перешли (и пустая строка — тоже)."""
    screen, oid = _screen(monkeypatch, has_electronics=1)
    screen.components_editor.add_row("ESP32", 1, 450)
    screen.components_editor.add_row()
    rows_before = list(screen.components_editor.rows)
    screen._on_electronics_commit()
    assert screen.components_editor.rows == rows_before
    db.set_components(oid, [{"name": "Экран", "qty": 1, "unit_cost": 700}])  # поменяли с другого компьютера
    screen.refresh()
    assert [r.name.value for r in screen.components_editor.rows] == ["Экран"]
